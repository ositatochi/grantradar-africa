from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Country, Sector
from apps.sources.models import Source

SOURCE_FILE = Path(settings.BASE_DIR) / "sources.yaml"


class Command(BaseCommand):
    help = "Load monitored sources from sources.yaml."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        path = SOURCE_FILE
        if not path.is_file():
            raise CommandError(f"Source file does not exist: {path}")

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, Mapping) or not isinstance(data.get("sources"), list):
            raise CommandError("sources.yaml must contain a top-level 'sources' list.")

        created_count = 0
        updated_count = 0
        for index, item in enumerate(data["sources"], start=1):
            if not isinstance(item, Mapping):
                raise CommandError(f"Source entry {index} must be a mapping.")

            defaults = self._source_defaults(item, index)
            source = Source(
                url=defaults["url"], **{k: v for k, v in defaults.items() if k != "url"}
            )
            try:
                source.full_clean(validate_unique=False)
            except ValidationError as error:
                raise CommandError(f"Invalid source entry {index}: {error}") from error

            country_codes = self._string_list(item.get("countries", []), "countries", index)
            sector_slugs = self._string_list(item.get("sectors", []), "sectors", index)
            countries = list(Country.objects.filter(alpha_2__in=country_codes))
            sectors = list(Sector.objects.filter(slug__in=sector_slugs))
            if {country.alpha_2 for country in countries} != set(country_codes):
                raise CommandError(f"Source entry {index} has an unknown country code.")
            if {sector.slug for sector in sectors} != set(sector_slugs):
                raise CommandError(f"Source entry {index} has an unknown sector slug.")

            _, created = Source.objects.update_or_create(url=source.url, defaults=defaults)
            loaded_source = Source.objects.get(url=source.url)
            loaded_source.countries.set(countries)
            loaded_source.sectors.set(sectors)
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Loaded sources: {created_count} created, {updated_count} updated.")
        )

    @staticmethod
    def _source_defaults(item: Mapping[str, Any], index: int) -> dict[str, Any]:
        required = {"name", "source_type", "url"}
        missing = required - item.keys()
        if missing:
            raise CommandError(f"Source entry {index} is missing: {', '.join(sorted(missing))}.")

        allowed = {
            "name",
            "source_type",
            "url",
            "crawl_frequency_hours",
            "adapter_class",
            "selectors",
            "reliability_score",
            "enabled",
        }
        unknown = set(item.keys()) - allowed - {"countries", "sectors"}
        if unknown:
            raise CommandError(
                f"Source entry {index} has unknown fields: {', '.join(sorted(unknown))}."
            )

        selectors = item.get("selectors", {})
        if not isinstance(selectors, Mapping):
            raise CommandError(f"Source entry {index}: selectors must be a mapping.")

        return {
            "name": item["name"],
            "source_type": item["source_type"],
            "crawl_frequency_hours": item.get("crawl_frequency_hours", 24),
            "adapter_class": item.get("adapter_class", ""),
            "selectors": dict(selectors),
            "reliability_score": item.get("reliability_score", 0.5),
            "enabled": item.get("enabled", True),
            "url": item["url"],
        }

    @staticmethod
    def _string_list(value: Any, field_name: str, index: int) -> list[str]:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise CommandError(f"Source entry {index}: {field_name} must be a list of strings.")
        return value
