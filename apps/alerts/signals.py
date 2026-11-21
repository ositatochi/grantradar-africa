from functools import partial

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.alerts.models import Alert
from apps.opportunities.models import Opportunity


def _is_public(opportunity: Opportunity) -> bool:
    return (
        opportunity.date_last_verified is not None
        and opportunity.status != Opportunity.Status.UNVERIFIED
        and bool(opportunity.official_source_url)
    )


@receiver(pre_save, sender=Opportunity)
def remember_public_visibility(
    sender: type[Opportunity], instance: Opportunity, **kwargs: object
) -> None:
    if instance.pk is None:
        instance.__dict__["_was_public"] = False
    else:
        previous = (
            Opportunity.objects.filter(pk=instance.pk)
            .values(
                "date_last_verified",
                "status",
                "official_source_url",
            )
            .first()
        )
        instance.__dict__["_was_public"] = bool(
            previous
            and previous["date_last_verified"] is not None
            and previous["status"] != Opportunity.Status.UNVERIFIED
            and previous["official_source_url"]
        )


@receiver(post_save, sender=Opportunity)
def queue_instant_alerts(
    sender: type[Opportunity],
    instance: Opportunity,
    created: bool,
    **kwargs: object,
) -> None:
    was_public = bool(instance.__dict__.pop("_was_public", False))
    if not (created or not was_public) or not _is_public(instance):
        return
    has_instant_alerts = Alert.objects.filter(
        is_active=True,
        channel=Alert.Channel.EMAIL,
        frequency=Alert.Frequency.INSTANT,
        consent_given_at__isnull=False,
        saved_search__is_active=True,
    ).exists()
    if has_instant_alerts:
        from apps.alerts.tasks import send_instant_alerts

        transaction.on_commit(partial(send_instant_alerts.delay, instance.pk))
