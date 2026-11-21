from __future__ import annotations

import gzip
import subprocess

import pytest
import scrapy
from django.core.management import call_command
from django.utils import timezone
from scrapy import Request
from scrapy.exceptions import IgnoreRequest
from scrapy.http import HtmlResponse

from apps.crawler.adapters import ConfiguredAdapter
from apps.crawler.models import RawDocument, SourceRun
from apps.crawler.pipelines import RawDocumentPipeline
from apps.crawler.spiders import MonitoredSourceSpider, PublicNetworkGuardMiddleware
from apps.sources.models import Source


def test_rss_adapter_produces_feed_and_record_snapshots() -> None:
    source = Source(source_type=Source.SourceType.RSS, selectors={})
    feed = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel><item><title>Call for proposals</title>
    <link>https://example.org/call</link><description>Apply now</description>
    </item></channel></rss>"""

    snapshots = list(ConfiguredAdapter(source).parse(feed, "https://example.org/feed", ""))

    assert len(snapshots) == 2
    assert snapshots[0].url == "https://example.org/feed"
    assert snapshots[1].url == "https://example.org/call"
    assert snapshots[1].is_record is True


def test_html_list_adapter_requires_item_selector() -> None:
    source = Source(source_type=Source.SourceType.HTML_LIST, selectors={})

    with pytest.raises(ValueError, match="CSS 'item' selector"):
        list(ConfiguredAdapter(source).parse(b"<html></html>", "https://example.org", "text/html"))


@pytest.mark.django_db
def test_load_sources_adds_ten_verified_feeds() -> None:
    call_command("seed_reference_data")
    call_command("load_sources")

    assert Source.objects.count() == 10
    assert Source.objects.filter(source_type=Source.SourceType.RSS, enabled=True).count() == 10


def test_public_network_guard_rejects_private_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "apps.crawler.spiders.socket.getaddrinfo",
        lambda *args, **kwargs: [(0, 0, 0, "", ("127.0.0.1", 0))],
    )

    with pytest.raises(IgnoreRequest, match="non-public"):
        PublicNetworkGuardMiddleware().process_request(
            Request("https://example.org/feed"),
            spider=scrapy.Spider(name="test"),
        )


@pytest.mark.django_db
def test_spider_persists_compressed_feed_and_entry_snapshots() -> None:
    source = Source.objects.create(
        name="Example RSS",
        source_type=Source.SourceType.RSS,
        url="https://example.org/feed",
    )
    run = SourceRun.objects.create(source=source, status=SourceRun.Status.RUNNING)
    body = b"""<rss><channel><item><title>Call</title>
    <link>https://example.org/call</link></item></channel></rss>"""
    spider = MonitoredSourceSpider(source_id=str(source.pk), source_run_id=str(run.pk))
    response = HtmlResponse(url=source.url, body=body, encoding="utf-8")
    items = list(spider.parse(response))
    pipeline = RawDocumentPipeline()

    for item in items:
        pipeline.process_item(item, spider)
    for item in items:
        pipeline.process_item(item, spider)

    run.refresh_from_db()
    documents = list(RawDocument.objects.filter(source=source).order_by("canonical_url"))
    assert run.pages_crawled == 1
    assert run.records_found == 1
    assert len(documents) == 2
    assert gzip.decompress(documents[0].compressed_content)


@pytest.mark.django_db
def test_crawl_task_updates_source_health(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.crawler.tasks import crawl_source

    source = Source.objects.create(
        name="Example RSS",
        source_type=Source.SourceType.RSS,
        url="https://example.org/feed",
    )

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        run_id = next(
            int(argument.removeprefix("source_run_id="))
            for argument in command
            if argument.startswith("source_run_id=")
        )
        run = SourceRun.objects.get(pk=run_id)
        run.pages_crawled = 1
        run.records_found = 2
        run.save(update_fields=["pages_crawled", "records_found"])
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("apps.crawler.tasks.subprocess.run", fake_run)

    assert crawl_source.run(source.pk) == 2

    source.refresh_from_db()
    run = SourceRun.objects.get(source=source)
    assert run.status == SourceRun.Status.SUCCEEDED
    assert run.completed_at is not None
    assert source.last_success_at is not None
    assert source.last_success_at <= timezone.now()
    assert source.last_record_count == 2
    assert source.failure_streak == 0
