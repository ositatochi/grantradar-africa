from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.crawler.models import SourceRun
from apps.sources.models import Source

logger = logging.getLogger(__name__)


@shared_task
def crawl_due_sources() -> int:
    now = timezone.now()
    queued = 0
    for source in Source.objects.filter(enabled=True).iterator():
        if source.last_success_at and source.last_success_at > now - timedelta(
            hours=source.crawl_frequency_hours
        ):
            continue
        task = crawl_source.apply_async(
            args=[source.pk],
            queue="playwright" if source.selectors.get("render_with_playwright") else "celery",
        )
        queued += 1
        logger.info("Queued source crawl", extra={"source_id": source.pk, "task_id": task.id})
    return queued


@shared_task
def crawl_source(source_id: int) -> int | None:
    now = timezone.now()
    with transaction.atomic():
        source = Source.objects.select_for_update().get(pk=source_id)
        if not source.enabled:
            return None
        active = SourceRun.objects.filter(
            source=source,
            status=SourceRun.Status.RUNNING,
            started_at__gte=now - timedelta(minutes=30),
        ).exists()
        if active:
            return None
        run = SourceRun.objects.create(
            source=source,
            status=SourceRun.Status.RUNNING,
            started_at=now,
        )

    environment = os.environ.copy()
    environment.setdefault("DJANGO_SETTINGS_MODULE", "grantradar.settings")
    command = [
        sys.executable,
        "-m",
        "apps.crawler.runner",
        "crawl",
        "monitored_source",
        "-a",
        f"source_id={source_id}",
        "-a",
        f"source_run_id={run.pk}",
    ]
    try:
        subprocess.run(
            command,
            cwd=settings.BASE_DIR,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        details = (
            (error.stderr or str(error))
            if isinstance(error, subprocess.CalledProcessError)
            else str(error)
        )
        run.status = SourceRun.Status.FAILED
        run.error_summary = details[-4000:]
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error_summary", "completed_at"])
        Source.objects.filter(pk=source_id).update(failure_streak=F("failure_streak") + 1)
        logger.exception("Source crawl failed", extra={"source_id": source_id, "run_id": run.pk})
        raise

    run.refresh_from_db()
    run.status = SourceRun.Status.SUCCEEDED
    run.completed_at = timezone.now()
    if run.records_found == 0:
        run.error_summary = "Fetch succeeded but discovered no records."
    run.save(update_fields=["status", "completed_at", "error_summary"])
    Source.objects.filter(pk=source_id).update(
        last_success_at=run.completed_at,
        last_record_count=run.records_found,
        failure_streak=0,
        average_yield=(F("average_yield") * 4 + run.records_found) / 5,
    )
    logger.info(
        "Source crawl completed",
        extra={"source_id": source_id, "run_id": run.pk, "records_found": run.records_found},
    )
    if run.records_found == 0:
        logger.warning("Source returned zero records", extra={"source_id": source_id})
    return run.records_found
