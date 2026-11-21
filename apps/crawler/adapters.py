from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import feedparser  # type: ignore[import-untyped]
from django.utils.module_loading import import_string
from selectolax.parser import HTMLParser

from apps.sources.models import Source


@dataclass(frozen=True)
class Snapshot:
    url: str
    content: bytes
    content_type: str
    is_record: bool = False


class SourceAdapter:
    def __init__(self, source: Source) -> None:
        self.source = source

    def parse(self, body: bytes, url: str, content_type: str) -> Iterator[Snapshot]:
        yield Snapshot(url, body, content_type)


class RSSAdapter(SourceAdapter):
    def parse(self, body: bytes, url: str, content_type: str) -> Iterator[Snapshot]:
        yield Snapshot(url, body, content_type)
        feed = feedparser.parse(body)
        for entry in feed.entries:
            item_url = entry.get("link")
            if not item_url:
                continue
            item_url = urljoin(url, item_url)
            item = {
                "title": entry.get("title", "")[:300],
                "url": item_url,
                "summary": entry.get("summary", "")[:2000],
                "published": entry.get("published", ""),
            }
            yield Snapshot(
                item_url,
                json.dumps(item, ensure_ascii=True).encode(),
                "application/json",
                is_record=True,
            )


class JSONAPIAdapter(SourceAdapter):
    def parse(self, body: bytes, url: str, content_type: str) -> Iterator[Snapshot]:
        yield Snapshot(url, body, content_type)
        payload: Any = json.loads(body)
        for key in self.source.selectors.get("items_path", "").split("."):
            if key:
                payload = payload[key]
        if not isinstance(payload, list):
            raise ValueError("JSON API items_path must resolve to a list.")
        url_field = self.source.selectors.get("url_field", "url")
        for item in payload:
            if not isinstance(item, Mapping) or not item.get(url_field):
                continue
            yield Snapshot(
                urljoin(url, str(item[url_field])),
                json.dumps(item, ensure_ascii=True, default=str).encode(),
                "application/json",
                is_record=True,
            )


class HTMLListAdapter(SourceAdapter):
    def parse(self, body: bytes, url: str, content_type: str) -> Iterator[Snapshot]:
        yield Snapshot(url, body, content_type)
        item_selector = self.source.selectors.get("item")
        link_selector = self.source.selectors.get("link", "a")
        if not item_selector:
            raise ValueError("HTML list sources require a CSS 'item' selector.")
        document = HTMLParser(body)
        for item in document.css(item_selector):
            link = item.css_first(link_selector)
            if link is None:
                continue
            item_url = urljoin(url, link.attributes.get("href", ""))
            if not item_url:
                continue
            title_selector = self.source.selectors.get("title")
            title_node = item.css_first(title_selector) if title_selector else link
            record = {
                "title": title_node.text(strip=True)[:300] if title_node else "",
                "url": item_url,
            }
            yield Snapshot(
                item_url,
                json.dumps(record, ensure_ascii=True).encode(),
                "application/json",
                is_record=True,
            )


class SitemapAdapter(SourceAdapter):
    def parse(self, body: bytes, url: str, content_type: str) -> Iterator[Snapshot]:
        yield Snapshot(url, body, content_type)
        root = ElementTree.fromstring(body)
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] == "loc" and node.text:
                item_url = urljoin(url, node.text.strip())
                yield Snapshot(
                    item_url,
                    json.dumps({"url": item_url}).encode(),
                    "application/json",
                    is_record=True,
                )


class ConfiguredAdapter:
    _types: dict[str, type[SourceAdapter]] = {
        Source.SourceType.API: JSONAPIAdapter,
        Source.SourceType.RSS: RSSAdapter,
        Source.SourceType.HTML_LIST: HTMLListAdapter,
        Source.SourceType.HTML_DETAIL: SourceAdapter,
        Source.SourceType.SITEMAP: SitemapAdapter,
    }

    def __init__(self, source: Source) -> None:
        self.source = source

    def parse(self, body: bytes, url: str, content_type: str) -> Iterator[Snapshot]:
        if self.source.adapter_class:
            adapter_class = import_string(self.source.adapter_class)
        else:
            adapter_class = self._types.get(self.source.source_type)
            if adapter_class is None:
                raise ValueError(
                    f"No adapter configured for source type {self.source.source_type!r}."
                )
        adapter = adapter_class(self.source)
        yield from adapter.parse(body, url, content_type)
