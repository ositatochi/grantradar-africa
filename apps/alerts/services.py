from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet
from django.http import QueryDict
from django.utils import timezone

from apps.alerts.models import Alert, SavedSearch
from apps.core.models import ApplicantType, Country, Currency, Sector, Theme
from apps.funders.models import Funder
from apps.opportunities.models import Opportunity
from apps.search.forms import OpportunitySearchForm
from apps.search.services import apply_search_filters, public_opportunities

MODEL_FIELDS: dict[
    str,
    type[ApplicantType]
    | type[Country]
    | type[Currency]
    | type[Funder]
    | type[Sector]
    | type[Theme],
] = {
    "applicant_type": ApplicantType,
    "country": Country,
    "currency": Currency,
    "funder": Funder,
    "sector": Sector,
    "theme": Theme,
}


def normalize_search_filters(data: QueryDict) -> dict[str, str]:
    form = OpportunitySearchForm(data)
    if not form.is_valid():
        raise ValueError("Search filters must be valid before they can be saved.")

    filters: dict[str, str] = {}
    for name, value in form.cleaned_data.items():
        if value is None or value is False or value == "":
            continue
        if name in MODEL_FIELDS:
            filters[name] = str(value.pk)
        elif isinstance(value, (date, datetime)):
            filters[name] = value.isoformat()
        elif isinstance(value, Decimal):
            filters[name] = str(value)
        elif value is True:
            filters[name] = "on"
        else:
            filters[name] = str(value)
    return filters


def saved_search_form(saved_search: SavedSearch) -> OpportunitySearchForm:
    data = dict(saved_search.filters)
    if saved_search.query:
        data["q"] = saved_search.query
    form = OpportunitySearchForm(data)
    if not form.is_valid():
        raise ValueError(f"Saved search {saved_search.pk} contains invalid filters.")
    return form


def matching_saved_search(saved_search: SavedSearch) -> QuerySet[Opportunity]:
    form = saved_search_form(saved_search)
    return apply_search_filters(public_opportunities(), form.cleaned_data)


def next_delivery_time(frequency: str, now: datetime | None = None) -> datetime:
    current = timezone.localtime(now or timezone.now())
    target = current.replace(hour=8, minute=0, second=0, microsecond=0)
    if frequency == Alert.Frequency.WEEKLY:
        days_until_monday = (7 - current.weekday()) % 7
        target += timedelta(days=days_until_monday)
        if target <= current:
            target += timedelta(days=7)
    elif frequency == Alert.Frequency.DAILY:
        if target <= current:
            target += timedelta(days=1)
    else:
        return now or timezone.now()
    return target


def display_filters(saved_search: SavedSearch) -> dict[str, Any]:
    filters = dict(saved_search.filters)
    if saved_search.query:
        filters["q"] = saved_search.query
    return filters
