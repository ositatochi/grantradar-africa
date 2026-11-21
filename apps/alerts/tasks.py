from __future__ import annotations

import logging
import smtplib
from datetime import datetime

from celery import shared_task
from django.conf import settings
from django.core.mail import BadHeaderError, send_mail
from django.db import transaction
from django.utils import timezone

from apps.alerts.models import Alert, AlertDelivery
from apps.alerts.services import matching_saved_search, next_delivery_time
from apps.opportunities.models import Opportunity
from apps.search.services import public_opportunities

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    pass


def _send_email_delivery(
    alert: Alert,
    opportunities: list[Opportunity],
    scheduled_at: datetime,
) -> AlertDelivery:
    delivery = AlertDelivery.objects.create(
        alert=alert,
        scheduled_at=scheduled_at,
        opportunity_ids=[opportunity.pk for opportunity in opportunities],
    )
    lines = [
        f"New opportunities for your saved search: {alert.saved_search.name}",
        "",
    ]
    for opportunity in opportunities:
        lines.extend(
            [
                opportunity.title,
                opportunity.official_source_url,
                "",
            ]
        )
    try:
        sent = send_mail(
            subject=f"New funding matches: {alert.saved_search.name}",
            message="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[alert.saved_search.owner.email],
            fail_silently=False,
        )
    except (BadHeaderError, OSError, smtplib.SMTPException) as error:
        delivery.status = AlertDelivery.Status.FAILED
        delivery.error_message = str(error)[:1000]
        delivery.save(update_fields=["status", "error_message"])
        logger.exception("Could not send alert delivery %s.", delivery.pk)
        raise EmailDeliveryError(f"Alert delivery {delivery.pk} failed.") from error

    if sent != 1:
        delivery.status = AlertDelivery.Status.FAILED
        delivery.error_message = "The email backend did not confirm delivery."
        delivery.save(update_fields=["status", "error_message"])
        logger.error("Email backend did not send alert delivery %s.", delivery.pk)
        raise EmailDeliveryError(f"Alert delivery {delivery.pk} was not accepted by the backend.")

    delivery.status = AlertDelivery.Status.SENT
    delivery.delivered_at = timezone.now()
    delivery.save(update_fields=["status", "delivered_at"])
    return delivery


def _alert_is_eligible(alert: Alert) -> bool:
    return (
        alert.is_active
        and alert.channel == Alert.Channel.EMAIL
        and alert.consent_given_at is not None
        and alert.saved_search.is_active
    )


@shared_task(
    autoretry_for=(EmailDeliveryError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_due_alerts() -> int:
    now = timezone.now()
    alert_ids = list(
        Alert.objects.filter(
            is_active=True,
            channel=Alert.Channel.EMAIL,
            consent_given_at__isnull=False,
            saved_search__is_active=True,
            frequency__in=[Alert.Frequency.DAILY, Alert.Frequency.WEEKLY],
            next_delivery_at__lte=now,
        ).values_list("pk", flat=True)
    )
    sent_count = 0
    for alert_id in alert_ids:
        with transaction.atomic():
            alert = (
                Alert.objects.select_for_update()
                .select_related("saved_search", "saved_search__owner")
                .filter(pk=alert_id, next_delivery_at__lte=now)
                .first()
            )
            if alert is None or not _alert_is_eligible(alert):
                continue
            scheduled_at = alert.next_delivery_at or now
            alert.next_delivery_at = next_delivery_time(alert.frequency, now)
            alert.save(update_fields=["next_delivery_at", "updated_at"])

        delivered_ids = {
            opportunity_id
            for delivery_ids in alert.deliveries.filter(
                status=AlertDelivery.Status.SENT
            ).values_list("opportunity_ids", flat=True)
            for opportunity_id in delivery_ids
        }
        matches = list(
            matching_saved_search(alert.saved_search)
            .filter(date_last_verified__gte=alert.created_at)
            .exclude(pk__in=delivered_ids)
            .select_related("funder", "currency")
            .order_by("-date_last_verified")[:10]
        )
        if not matches:
            continue
        try:
            delivery = _send_email_delivery(alert, matches, scheduled_at)
        except EmailDeliveryError:
            alert.next_delivery_at = scheduled_at
            alert.save(update_fields=["next_delivery_at", "updated_at"])
            raise
        if delivery.status == AlertDelivery.Status.SENT:
            sent_count += 1
    return sent_count


@shared_task(
    autoretry_for=(EmailDeliveryError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_instant_alerts(opportunity_id: int) -> int:
    opportunity = public_opportunities().filter(pk=opportunity_id).first()
    if opportunity is None:
        return 0

    alerts = Alert.objects.filter(
        is_active=True,
        channel=Alert.Channel.EMAIL,
        frequency=Alert.Frequency.INSTANT,
        consent_given_at__isnull=False,
        saved_search__is_active=True,
    ).select_related("saved_search", "saved_search__owner")
    sent_count = 0
    for alert in alerts:
        if not _alert_is_eligible(alert):
            continue
        if not matching_saved_search(alert.saved_search).filter(pk=opportunity.pk).exists():
            continue
        prior_ids = {
            opportunity_id
            for delivery in alert.deliveries.filter(status=AlertDelivery.Status.SENT).only(
                "opportunity_ids"
            )
            for opportunity_id in delivery.opportunity_ids
        }
        if opportunity.pk in prior_ids:
            continue
        delivery = _send_email_delivery(alert, [opportunity], timezone.now())
        if delivery.status == AlertDelivery.Status.SENT:
            sent_count += 1
    return sent_count
