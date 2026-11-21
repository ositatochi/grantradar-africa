from __future__ import annotations

import socket
from collections.abc import Iterator
from ipaddress import ip_address
from urllib.parse import urlparse

import scrapy
from scrapy.exceptions import IgnoreRequest
from w3lib.url import canonicalize_url

from apps.crawler.adapters import ConfiguredAdapter
from apps.crawler.items import SnapshotItem
from apps.sources.models import Source


class PublicNetworkGuardMiddleware:
    def process_request(self, request: scrapy.Request, spider: scrapy.Spider) -> None:
        parsed = urlparse(request.url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise IgnoreRequest("Only public HTTP(S) URLs are allowed.")
        try:
            addresses = {
                ip_address(result[4][0])
                for result in socket.getaddrinfo(parsed.hostname, None, type=socket.SOCK_STREAM)
            }
        except (OSError, ValueError) as error:
            raise IgnoreRequest("Unable to resolve source host.") from error
        if not addresses or any(not address.is_global for address in addresses):
            raise IgnoreRequest("Source resolves to a non-public IP address.")


class MonitoredSourceSpider(scrapy.Spider):
    name = "monitored_source"

    def __init__(self, source_id: str, source_run_id: str, *args: str, **kwargs: str) -> None:
        super().__init__(*args, **kwargs)
        self.source_id = int(source_id)
        self.source_run_id = int(source_run_id)
        self.source = Source.objects.get(pk=self.source_id)
        self.adapter = ConfiguredAdapter(self.source)

    def start_requests(self) -> Iterator[scrapy.Request]:
        yield scrapy.Request(
            self.source.url,
            callback=self.parse,
            meta={"playwright": self.source.selectors.get("render_with_playwright", False)},
        )

    def parse(self, response: scrapy.http.Response) -> Iterator[SnapshotItem]:
        from django.db.models import F

        from apps.crawler.models import SourceRun

        SourceRun.objects.filter(pk=self.source_run_id).update(pages_crawled=F("pages_crawled") + 1)
        for snapshot in self.adapter.parse(
            response.body,
            response.url,
            (response.headers.get(b"Content-Type") or b"").decode("latin-1"),
        ):
            if snapshot.is_record:
                SourceRun.objects.filter(pk=self.source_run_id).update(
                    records_found=F("records_found") + 1
                )
            yield {
                "source_id": self.source_id,
                "source_run_id": self.source_run_id,
                "url": snapshot.url,
                "canonical_url": canonicalize_url(snapshot.url),
                "content": snapshot.content,
                "content_type": snapshot.content_type,
                "status_code": response.status,
                "etag": (response.headers.get(b"ETag") or b"").decode("latin-1"),
                "last_modified": (response.headers.get(b"Last-Modified") or b"").decode("latin-1"),
            }
