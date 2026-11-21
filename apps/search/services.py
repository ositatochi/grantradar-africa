from __future__ import annotations

import json
from datetime import date
from typing import Any

from django.core.paginator import Page, Paginator
from django.db.models import F, Q, QuerySet

from apps.opportunities.models import Opportunity
from apps.search.indexing import search_index

PAGE_SIZE = 20


def public_opportunities() -> QuerySet[Opportunity]:
    return (
        Opportunity.objects.filter(date_last_verified__isnull=False)
        .exclude(status=Opportunity.Status.UNVERIFIED)
        .exclude(official_source_url="")
    )


def apply_search_filters(
    queryset: QuerySet[Opportunity],
    filters: dict[str, Any],
) -> QuerySet[Opportunity]:
    if query := filters.get("q"):
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(funder_name__icontains=query)
            | Q(funder__name__icontains=query)
            | Q(programme_name__icontains=query)
            | Q(summary__icontains=query)
            | Q(description_snippet__icontains=query)
        )
    if country := filters.get("country"):
        queryset = queryset.filter(
            Q(eligible_countries=country) | Q(eligible_countries__isnull=True)
        )
    if region := filters.get("region"):
        queryset = queryset.filter(
            Q(eligible_countries__region=region) | Q(eligible_countries__isnull=True)
        )
    if sector := filters.get("sector"):
        queryset = queryset.filter(sectors=sector)
    if theme := filters.get("theme"):
        queryset = queryset.filter(themes=theme)
    if funder := filters.get("funder"):
        queryset = queryset.filter(funder=funder)
    if funder_type := filters.get("funder_type"):
        queryset = queryset.filter(funder__funder_type=funder_type)
    if opportunity_type := filters.get("opportunity_type"):
        queryset = queryset.filter(opportunity_type=opportunity_type)
    if applicant_type := filters.get("applicant_type"):
        queryset = queryset.filter(applicant_types=applicant_type)
    if currency := filters.get("currency"):
        queryset = queryset.filter(currency=currency)
    if language := filters.get("language"):
        queryset = queryset.filter(language=language)
    if status := filters.get("status"):
        queryset = queryset.filter(status=status)
    if (minimum := filters.get("min_amount_usd")) is not None:
        queryset = queryset.filter(amount_usd__gte=minimum)
    if (maximum := filters.get("max_amount_usd")) is not None:
        queryset = queryset.filter(amount_usd__lte=maximum)
    if start := filters.get("deadline_after"):
        queryset = queryset.filter(deadline_date__gte=start)
    if end := filters.get("deadline_before"):
        queryset = queryset.filter(deadline_date__lte=end)
    if filters.get("no_match"):
        queryset = queryset.filter(co_funding_required=False)
    if filters.get("individuals_allowed"):
        queryset = queryset.filter(applicant_types__slug="individual")
    return queryset.distinct()


def order_opportunities(
    queryset: QuerySet[Opportunity],
    sort: str,
) -> QuerySet[Opportunity]:
    if sort == "deadline":
        return queryset.order_by(F("deadline_date").asc(nulls_last=True), "title")
    if sort == "newest":
        return queryset.order_by("-date_first_found", "-created_at")
    if sort == "amount":
        return queryset.order_by(F("amount_usd").desc(nulls_last=True), "title")
    return queryset.order_by("-date_first_found", "-created_at")


def meilisearch_filters(filters: dict[str, Any]) -> list[str | list[str]]:
    result: list[str | list[str]] = []
    if value := filters.get("status"):
        result.append(_equals("status", value))
    if country := filters.get("country"):
        result.append(
            [
                _equals("eligible_country_codes", country.alpha_2),
                "eligible_country_codes IS EMPTY",
            ]
        )
    if region := filters.get("region"):
        result.append(
            [
                _equals("eligible_regions", region),
                "eligible_country_codes IS EMPTY",
            ]
        )
    if sector := filters.get("sector"):
        result.append(_equals("sector_slugs", sector.slug))
    if theme := filters.get("theme"):
        result.append(_equals("theme_slugs", theme.slug))
    if funder := filters.get("funder"):
        result.append(_equals("funder_slug", funder.slug))
    if funder_type := filters.get("funder_type"):
        result.append(_equals("funder_type", funder_type))
    if opportunity_type := filters.get("opportunity_type"):
        result.append(_equals("opportunity_type", opportunity_type))
    if applicant_type := filters.get("applicant_type"):
        result.append(_equals("applicant_type_slugs", applicant_type.slug))
    if currency := filters.get("currency"):
        result.append(_equals("currency_code", currency.code))
    if language := filters.get("language"):
        result.append(_equals("language", language))
    if (minimum := filters.get("min_amount_usd")) is not None:
        result.append(f"amount_usd >= {minimum}")
    if (maximum := filters.get("max_amount_usd")) is not None:
        result.append(f"amount_usd <= {maximum}")
    if start := filters.get("deadline_after"):
        result.append(f"deadline_ordinal >= {_ordinal(start)}")
    if end := filters.get("deadline_before"):
        result.append(f"deadline_ordinal <= {_ordinal(end)}")
    if filters.get("no_match"):
        result.append("co_funding_required = false")
    if filters.get("individuals_allowed"):
        result.append(_equals("applicant_type_slugs", "individual"))
    return result


def meilisearch_sort(sort: str) -> list[str]:
    if sort == "deadline":
        return ["deadline_ordinal:asc"]
    if sort == "newest":
        return ["date_first_found_ordinal:desc"]
    if sort == "amount":
        return ["amount_usd:desc"]
    return []


def paginated_meilisearch_results(
    queryset: QuerySet[Opportunity],
    query: str,
    filters: dict[str, Any],
    requested_page: str | None,
) -> tuple[Page[Opportunity] | None, str]:
    paginator = Paginator(queryset, PAGE_SIZE)
    requested = paginator.get_page(requested_page)
    page_number = requested.number
    sort = filters.get("sort", "relevance")
    meili_filters = meilisearch_filters(filters)
    meili_sort = meilisearch_sort(sort)
    response, warning = search_index(query, meili_filters, meili_sort, page_number, PAGE_SIZE)
    if response is None:
        return None, warning

    hits = response.get("hits", [])
    hit_ids = [str(hit["id"]) for hit in hits if "id" in hit]
    objects_by_id = {
        str(opportunity.pk): opportunity
        for opportunity in queryset.filter(pk__in=hit_ids)
        .select_related("funder", "currency")
        .prefetch_related(
            "eligible_countries",
            "sectors",
            "themes",
            "applicant_types",
            "source_links__source",
        )
    }
    results = [objects_by_id[hit_id] for hit_id in hit_ids if hit_id in objects_by_id]
    page = Page(results, page_number, paginator)
    return page, warning


def opportunity_queryset_for_display(
    queryset: QuerySet[Opportunity],
) -> QuerySet[Opportunity]:
    return queryset.select_related("funder", "currency").prefetch_related(
        "eligible_countries",
        "sectors",
        "themes",
        "applicant_types",
        "source_links__source",
    )


def _equals(attribute: str, value: str) -> str:
    return f"{attribute} = {json.dumps(value)}"


def _ordinal(value: date) -> int:
    return value.toordinal()
