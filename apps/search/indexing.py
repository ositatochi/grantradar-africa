from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings
from meilisearch import Client
from meilisearch.errors import MeilisearchApiError, MeilisearchCommunicationError
from meilisearch.index import Index

from apps.opportunities.models import Opportunity

logger = logging.getLogger(__name__)
OPPORTUNITY_INDEX = "opportunities"
FILTERABLE_ATTRIBUTES = [
    "status",
    "funder_slug",
    "funder_type",
    "opportunity_type",
    "eligible_country_codes",
    "eligible_regions",
    "sector_slugs",
    "theme_slugs",
    "applicant_type_slugs",
    "currency_code",
    "language",
    "co_funding_required",
    "deadline_ordinal",
    "amount_usd",
]
SORTABLE_ATTRIBUTES = [
    "deadline_ordinal",
    "date_first_found_ordinal",
    "amount_usd",
]


def get_meilisearch_client() -> Client | None:
    if not settings.MEILI_URL:
        return None
    return Client(settings.MEILI_URL, settings.MEILI_MASTER_KEY or None)


def get_or_create_opportunity_index(client: Client) -> Index:
    try:
        return client.get_index(OPPORTUNITY_INDEX)
    except MeilisearchApiError as error:
        if error.code != "index_not_found":
            raise

    task = client.create_index(OPPORTUNITY_INDEX, {"primaryKey": "id"})
    client.wait_for_task(task.task_uid, timeout_in_ms=60_000)
    index = client.index(OPPORTUNITY_INDEX)
    task = index.update_settings(
        {
            "filterableAttributes": FILTERABLE_ATTRIBUTES,
            "sortableAttributes": SORTABLE_ATTRIBUTES,
        }
    )
    client.wait_for_task(task.task_uid, timeout_in_ms=60_000)
    return index


def configure_opportunity_index(client: Client) -> Index:
    index = get_or_create_opportunity_index(client)
    task = index.update_settings(
        {
            "filterableAttributes": FILTERABLE_ATTRIBUTES,
            "sortableAttributes": SORTABLE_ATTRIBUTES,
        }
    )
    client.wait_for_task(task.task_uid, timeout_in_ms=60_000)
    return index


def is_public_opportunity(opportunity: Opportunity) -> bool:
    return (
        opportunity.date_last_verified is not None
        and opportunity.status != Opportunity.Status.UNVERIFIED
        and bool(opportunity.official_source_url)
    )


def opportunity_document(opportunity: Opportunity) -> dict[str, Any]:
    eligible_countries = list(opportunity.eligible_countries.all())
    return {
        "id": str(opportunity.pk),
        "title": opportunity.title,
        "funder_name": opportunity.funder.name if opportunity.funder else opportunity.funder_name,
        "funder_slug": opportunity.funder.slug if opportunity.funder else "",
        "funder_type": opportunity.funder.funder_type if opportunity.funder else "",
        "programme_name": opportunity.programme_name,
        "summary": opportunity.summary,
        "description_snippet": opportunity.description_snippet,
        "status": opportunity.status,
        "opportunity_type": opportunity.opportunity_type,
        "deadline_ordinal": (
            opportunity.deadline_date.toordinal() if opportunity.deadline_date else None
        ),
        "date_first_found_ordinal": (
            opportunity.date_first_found.date().toordinal()
            if opportunity.date_first_found
            else None
        ),
        "amount_usd": _index_number(opportunity.amount_usd),
        "currency_code": opportunity.currency.code if opportunity.currency else "",
        "eligible_country_codes": [country.alpha_2 for country in eligible_countries],
        "eligible_regions": sorted(
            {country.region for country in eligible_countries if country.region}
        ),
        "sector_slugs": list(opportunity.sectors.values_list("slug", flat=True)),
        "theme_slugs": list(opportunity.themes.values_list("slug", flat=True)),
        "applicant_type_slugs": list(opportunity.applicant_types.values_list("slug", flat=True)),
        "co_funding_required": opportunity.co_funding_required,
        "language": opportunity.language,
        "official_source_url": opportunity.official_source_url,
        "date_last_verified": (
            opportunity.date_last_verified.isoformat() if opportunity.date_last_verified else None
        ),
    }


def _index_number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def rebuild_opportunity_index(batch_size: int = 500) -> int:
    client = get_meilisearch_client()
    if client is None:
        raise RuntimeError("MEILI_URL must be configured before rebuilding the search index.")

    index = configure_opportunity_index(client)
    task = index.delete_all_documents()
    client.wait_for_task(task.task_uid, timeout_in_ms=60_000)

    queryset = (
        Opportunity.objects.filter(date_last_verified__isnull=False)
        .exclude(status=Opportunity.Status.UNVERIFIED)
        .exclude(official_source_url="")
        .select_related("funder", "currency")
        .prefetch_related(
            "eligible_countries",
            "sectors",
            "themes",
            "applicant_types",
        )
        .order_by("pk")
    )
    count = 0
    batch: list[dict[str, Any]] = []
    for opportunity in queryset.iterator(chunk_size=batch_size):
        batch.append(opportunity_document(opportunity))
        if len(batch) == batch_size:
            task = index.add_documents(batch, primary_key="id")
            client.wait_for_task(task.task_uid, timeout_in_ms=60_000)
            count += len(batch)
            batch.clear()

    if batch:
        task = index.add_documents(batch, primary_key="id")
        client.wait_for_task(task.task_uid, timeout_in_ms=60_000)
        count += len(batch)
    return count


def search_index(
    query: str,
    filters: list[str | list[str]],
    sort: list[str],
    page: int,
    page_size: int,
) -> tuple[dict[str, Any] | None, str]:
    client = get_meilisearch_client()
    if client is None:
        return None, "The search index is not configured; keyword search is using the database."

    params: dict[str, Any] = {"hitsPerPage": page_size, "page": page}
    if filters:
        params["filter"] = filters
    if sort:
        params["sort"] = sort
    try:
        return client.index(OPPORTUNITY_INDEX).search(query, params), ""
    except MeilisearchApiError as error:
        if error.code != "index_not_found":
            raise
        logger.warning("Meilisearch opportunity index is missing; using database search.")
        return (
            None,
            "The search index has not been built yet; keyword search is using the database.",
        )
    except MeilisearchCommunicationError:
        logger.warning("Meilisearch is unavailable; using database search.", exc_info=True)
        return (
            None,
            "Search is temporarily using database results because the service is unavailable.",
        )
