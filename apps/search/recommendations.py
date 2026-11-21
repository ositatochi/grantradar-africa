from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Q

from apps.accounts.models import User
from apps.core.models import Sector
from apps.opportunities.models import Opportunity
from apps.search.services import opportunity_queryset_for_display, public_opportunities


@dataclass(frozen=True)
class OpportunityRecommendation:
    opportunity: Opportunity
    score: int


def recommendations_for(user: User, limit: int = 6) -> list[OpportunityRecommendation]:
    profile_sector_ids = set(user.profile_sectors.values_list("pk", flat=True))
    target_country_ids = set(user.profile_countries.values_list("pk", flat=True))
    behavior_sector_ids = set(
        Sector.objects.filter(
            Q(opportunities__bookmarks__owner_id=user.pk)
            | Q(opportunities__pipeline_items__owner_id=user.pk)
        )
        .values_list("pk", flat=True)
        .distinct()
    )
    candidates = (
        public_opportunities()
        .exclude(bookmarks__owner_id=user.pk)
        .exclude(pipeline_items__owner_id=user.pk)
        .distinct()
        .order_by("-date_last_verified")[:500]
    )
    opportunities = opportunity_queryset_for_display(candidates)
    ranked: list[OpportunityRecommendation] = []
    for opportunity in opportunities:
        score = _score_opportunity(
            opportunity,
            profile_sector_ids,
            target_country_ids,
            behavior_sector_ids,
            user.budget_min_usd,
            user.budget_max_usd,
        )
        if score:
            ranked.append(OpportunityRecommendation(opportunity=opportunity, score=score))
    ranked.sort(
        key=lambda recommendation: (
            -recommendation.score,
            recommendation.opportunity.deadline_date or date.max,
            recommendation.opportunity.title.casefold(),
        )
    )
    return ranked[: max(limit, 0)]


def _score_opportunity(
    opportunity: Opportunity,
    profile_sector_ids: set[int],
    target_country_ids: set[int],
    behavior_sector_ids: set[int],
    budget_min_usd: Decimal | None,
    budget_max_usd: Decimal | None,
) -> int:
    opportunity_sector_ids = {sector.pk for sector in opportunity.sectors.all()}
    opportunity_country_ids = {country.pk for country in opportunity.eligible_countries.all()}
    score = 3 * len(profile_sector_ids & opportunity_sector_ids)
    score += 2 * len(behavior_sector_ids & opportunity_sector_ids)
    if target_country_ids and opportunity_country_ids & target_country_ids:
        score += 2
    elif not opportunity_country_ids:
        score += 1

    amount = opportunity.amount_usd
    if amount is not None:
        above_minimum = budget_min_usd is None or amount >= budget_min_usd
        below_maximum = budget_max_usd is None or amount <= budget_max_usd
        if above_minimum and below_maximum:
            score += 1
    return score
