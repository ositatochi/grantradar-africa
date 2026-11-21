from __future__ import annotations

from functools import partial

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.opportunities.models import Opportunity
from apps.search.tasks import sync_opportunity


def _queue_sync(opportunity_id: int) -> None:
    if settings.MEILI_URL:
        transaction.on_commit(partial(sync_opportunity.delay, opportunity_id))


@receiver(post_save, sender=Opportunity)
def schedule_opportunity_sync(
    sender: type[Opportunity],
    instance: Opportunity,
    **kwargs: object,
) -> None:
    _queue_sync(instance.pk)


@receiver(post_delete, sender=Opportunity)
def schedule_opportunity_delete(
    sender: type[Opportunity],
    instance: Opportunity,
    **kwargs: object,
) -> None:
    _queue_sync(instance.pk)
