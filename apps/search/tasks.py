from __future__ import annotations

import logging

from celery import shared_task
from meilisearch.errors import MeilisearchCommunicationError

from apps.opportunities.models import Opportunity
from apps.search.indexing import (
    get_meilisearch_client,
    get_or_create_opportunity_index,
    is_public_opportunity,
    opportunity_document,
)

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(MeilisearchCommunicationError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def sync_opportunity(opportunity_id: int) -> None:
    client = get_meilisearch_client()
    if client is None:
        return
    index = get_or_create_opportunity_index(client)
    try:
        opportunity = (
            Opportunity.objects.select_related("funder", "currency")
            .prefetch_related(
                "eligible_countries",
                "sectors",
                "themes",
                "applicant_types",
            )
            .get(pk=opportunity_id)
        )
    except Opportunity.DoesNotExist:
        task = index.delete_document(str(opportunity_id))
        client.wait_for_task(task.task_uid, timeout_in_ms=60_000)
        return
    if not is_public_opportunity(opportunity):
        task = index.delete_document(str(opportunity_id))
        client.wait_for_task(task.task_uid, timeout_in_ms=60_000)
        return
    task = index.update_documents([opportunity_document(opportunity)], primary_key="id")
    client.wait_for_task(task.task_uid, timeout_in_ms=60_000)
    logger.info("Indexed public opportunity", extra={"opportunity_id": opportunity_id})
