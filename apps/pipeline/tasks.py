from __future__ import annotations

from celery import shared_task

from apps.crawler.models import RawDocument
from apps.pipeline.services import expire_opportunities as close_expired
from apps.pipeline.services import process_document


@shared_task
def process_pending_documents(
    source_id: int | None = None,
    source_run_id: int | None = None,
    limit: int = 100,
) -> int:
    pending = RawDocument.objects.filter(processing_status=RawDocument.ProcessingStatus.PENDING)
    if source_id is not None:
        pending = pending.filter(source_id=source_id)
    if source_run_id is not None:
        pending = pending.filter(source_run_id=source_run_id)
    document_ids = list(pending.order_by("pk").values_list("pk", flat=True)[:limit])
    processed = 0
    for document_id in document_ids:
        if process_document(document_id) is not None:
            processed += 1
    return processed


@shared_task
def expire_opportunities() -> int:
    return close_expired()
