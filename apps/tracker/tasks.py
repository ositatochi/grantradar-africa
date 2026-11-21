from __future__ import annotations

import logging
import smtplib
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import BadHeaderError, send_mail
from django.utils import timezone

from apps.opportunities.models import Opportunity
from apps.tracker.models import DeadlineReminder, PipelineItem

logger = logging.getLogger(__name__)
REMINDER_INTERVALS = (14, 7, 3, 1)


class DeadlineReminderDeliveryError(Exception):
    pass


@shared_task(
    autoretry_for=(DeadlineReminderDeliveryError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_deadline_reminders() -> int:
    today = timezone.localdate()
    target_dates = [today + timedelta(days=days) for days in REMINDER_INTERVALS]
    items = (
        PipelineItem.objects.filter(
            owner__is_active=True,
            owner__deadline_reminders_enabled=True,
            status__in=[
                PipelineItem.Status.INTERESTED,
                PipelineItem.Status.PREPARING,
                PipelineItem.Status.SUBMITTED,
            ],
            opportunity__deadline_date__in=target_dates,
            opportunity__date_last_verified__isnull=False,
            opportunity__status__in=[
                Opportunity.Status.OPEN,
                Opportunity.Status.CLOSING_SOON,
                Opportunity.Status.ROLLING,
                Opportunity.Status.UPCOMING,
            ],
        )
        .exclude(opportunity__official_source_url="")
        .exclude(opportunity__status="unverified")
        .select_related("owner", "opportunity")
    )
    sent_count = 0
    for item in items:
        deadline = item.opportunity.deadline_date
        if deadline is None:
            continue
        days_before = (deadline - today).days
        reminder, created = DeadlineReminder.objects.get_or_create(
            pipeline_item=item,
            deadline_date=deadline,
            days_before=days_before,
        )
        if not created and reminder.status == DeadlineReminder.Status.SENT:
            continue
        url = f"{settings.SITE_URL.rstrip('/')}{item.opportunity.get_absolute_url()}"
        try:
            sent = send_mail(
                subject=f"Funding deadline in {days_before} day(s): {item.opportunity.title}",
                message=(
                    f"The deadline for {item.opportunity.title} is {deadline:%d %B %Y}.\n\n"
                    f"Official source: {item.opportunity.official_source_url}\n"
                    f"GrantRadar details: {url}\n"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[item.owner.email],
                fail_silently=False,
            )
        except (BadHeaderError, OSError, smtplib.SMTPException) as error:
            reminder.status = DeadlineReminder.Status.FAILED
            reminder.error_message = str(error)[:1000]
            reminder.save(update_fields=["status", "error_message"])
            logger.exception("Could not send deadline reminder %s.", reminder.pk)
            raise DeadlineReminderDeliveryError(
                f"Deadline reminder {reminder.pk} failed."
            ) from error
        if sent != 1:
            reminder.status = DeadlineReminder.Status.FAILED
            reminder.error_message = "The email backend did not confirm delivery."
            reminder.save(update_fields=["status", "error_message"])
            logger.error("Email backend did not send deadline reminder %s.", reminder.pk)
            raise DeadlineReminderDeliveryError(
                f"Deadline reminder {reminder.pk} was not accepted by the backend."
            )
        reminder.status = DeadlineReminder.Status.SENT
        reminder.sent_at = timezone.now()
        reminder.error_message = ""
        reminder.save(update_fields=["status", "sent_at", "error_message"])
        sent_count += 1
    return sent_count
