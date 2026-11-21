from __future__ import annotations

import gzip
import hashlib

from django import setup
from django.apps import apps
from django.db import IntegrityError
from scrapy import Spider
from scrapy.exceptions import DropItem

from apps.crawler.items import SnapshotItem


class RawDocumentPipeline:
    def open_spider(self, spider: Spider) -> None:
        if not apps.ready:
            setup()

    def process_item(self, item: SnapshotItem, spider: Spider) -> SnapshotItem:
        from apps.crawler.models import RawDocument

        content = item["content"]
        content_hash = hashlib.sha256(content).hexdigest()
        try:
            RawDocument.objects.get_or_create(
                source_id=item["source_id"],
                canonical_url=item["canonical_url"],
                content_hash=content_hash,
                defaults={
                    "source_run_id": item["source_run_id"],
                    "url": item["url"],
                    "content_type": item["content_type"],
                    "status_code": item["status_code"],
                    "compressed_content": gzip.compress(content),
                    "etag": item["etag"],
                    "last_modified": item["last_modified"],
                },
            )
        except IntegrityError as error:
            raise DropItem(f"Could not persist snapshot {item['canonical_url']}.") from error
        return item
