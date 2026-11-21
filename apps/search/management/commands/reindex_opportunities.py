from typing import Any

from django.core.management.base import BaseCommand, CommandError
from meilisearch.errors import MeilisearchApiError, MeilisearchCommunicationError

from apps.search.indexing import get_meilisearch_client, rebuild_opportunity_index


class Command(BaseCommand):
    help = "Rebuild the public opportunity search index in Meilisearch."

    def handle(self, *args: Any, **options: Any) -> None:
        if get_meilisearch_client() is None:
            raise CommandError("Set MEILI_URL before rebuilding the search index.")
        try:
            count = rebuild_opportunity_index()
        except (MeilisearchApiError, MeilisearchCommunicationError, TimeoutError) as error:
            raise CommandError(f"Unable to rebuild the opportunity index: {error}") from error
        self.stdout.write(self.style.SUCCESS(f"Indexed {count} verified opportunities."))
