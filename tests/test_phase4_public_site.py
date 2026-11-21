from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import ApplicantType, Country, Currency, Sector, Theme
from apps.funders.models import Funder
from apps.opportunities.models import ErrorReport, Opportunity
from apps.pipeline.services import expire_opportunities


def make_opportunity(
    title: str,
    *,
    status: str = Opportunity.Status.OPEN,
    co_funding_required: bool | None = None,
) -> Opportunity:
    return Opportunity.objects.create(
        title=title,
        funder_name="Example Funder",
        opportunity_type=Opportunity.OpportunityType.GRANT,
        official_source_url=f"https://example.org/{title.lower().replace(' ', '-')}",
        status=status,
        date_last_verified=timezone.now() if status != Opportunity.Status.UNVERIFIED else None,
        deadline_date=timezone.localdate() + timedelta(days=20),
        summary=f"Funding for {title.lower()} work.",
        co_funding_required=co_funding_required,
    )


@pytest.mark.django_db
@override_settings(MEILI_URL="")
def test_home_and_details_only_show_verified_opportunities(client) -> None:
    public = make_opportunity("Verified climate grant")
    make_opportunity("Unverified climate grant", status=Opportunity.Status.UNVERIFIED)

    home_response = client.get(reverse("search:home"))
    detail_response = client.get(public.get_absolute_url())

    assert home_response.status_code == 200
    assert b"Verified climate grant" in home_response.content
    assert b"Unverified climate grant" not in home_response.content
    assert detail_response.status_code == 200
    assert b"https://example.org/verified-climate-grant" in detail_response.content
    assert b"Last verified" in detail_response.content


@pytest.mark.django_db
@override_settings(MEILI_URL="")
def test_search_filters_country_and_only_explicit_no_match_records(client) -> None:
    nigeria = Country.objects.create(alpha_2="NG", alpha_3="NGA", name="Nigeria", region="Africa")
    kenya = Country.objects.create(alpha_2="KE", alpha_3="KEN", name="Kenya", region="Africa")
    eligible = make_opportunity("Climate fund for Nigeria", co_funding_required=False)
    eligible.eligible_countries.add(nigeria)
    make_opportunity("Climate fund for all", co_funding_required=False)
    foreign = make_opportunity("Climate fund for Kenya", co_funding_required=False)
    foreign.eligible_countries.add(kenya)
    make_opportunity("Climate fund with unknown match", co_funding_required=None)

    response = client.get(
        reverse("search:opportunity-list"),
        {
            "q": "climate",
            "country": str(nigeria.pk),
            "no_match": "on",
        },
    )

    assert response.status_code == 200
    assert b"Climate fund for Nigeria" in response.content
    assert b"Climate fund for all" in response.content
    assert b"Climate fund for Kenya" not in response.content
    assert b"Climate fund with unknown match" not in response.content


@pytest.mark.django_db
@override_settings(MEILI_URL="")
def test_search_applies_funder_taxonomy_amount_and_deadline_filters(client) -> None:
    funder = Funder.objects.create(
        name="Climate Foundation",
        funder_type=Funder.FunderType.FOUNDATION,
    )
    sector = Sector.objects.create(name="Climate Test", slug="climate-test")
    theme = Theme.objects.create(name="Youth Test", slug="youth-test")
    applicant = ApplicantType.objects.create(name="Individual Test", slug="individual")
    currency = Currency.objects.create(code="USD", name="US Dollar", is_active=True)
    opportunity = make_opportunity("Climate fellowship")
    opportunity.funder = funder
    opportunity.amount_usd = 150
    opportunity.currency = currency
    opportunity.language = "en"
    opportunity.save()
    opportunity.sectors.add(sector)
    opportunity.themes.add(theme)
    opportunity.applicant_types.add(applicant)

    response = client.get(
        reverse("search:opportunity-list"),
        {
            "funder": str(funder.pk),
            "funder_type": Funder.FunderType.FOUNDATION,
            "sector": str(sector.pk),
            "theme": str(theme.pk),
            "opportunity_type": Opportunity.OpportunityType.GRANT,
            "applicant_type": str(applicant.pk),
            "currency": str(currency.pk),
            "language": "en",
            "status": Opportunity.Status.OPEN,
            "min_amount_usd": "100",
            "max_amount_usd": "200",
            "deadline_after": (timezone.localdate() + timedelta(days=10)).isoformat(),
            "deadline_before": (timezone.localdate() + timedelta(days=30)).isoformat(),
            "sort": "deadline",
        },
    )

    assert response.status_code == 200
    assert b"Climate fellowship" in response.content


@pytest.mark.django_db
@override_settings(MEILI_URL="")
def test_funder_directory_and_error_report_use_public_opportunity(client) -> None:
    funder = Funder.objects.create(
        name="Example Foundation",
        funder_type=Funder.FunderType.FOUNDATION,
        website="https://example.org",
    )
    opportunity = make_opportunity("Community health grant")
    opportunity.funder = funder
    opportunity.save()

    directory_response = client.get(reverse("search:funder-list"))
    detail_response = client.get(reverse("search:funder-detail", kwargs={"slug": funder.slug}))
    report_response = client.post(
        reverse(
            "search:report-error",
            kwargs={"pk": opportunity.pk, "slug": "community-health-grant"},
        ),
        {"description": "The deadline has changed."},
    )

    assert directory_response.status_code == 200
    assert b"Example Foundation" in directory_response.content
    assert detail_response.status_code == 200
    assert b"Community health grant" in detail_response.content
    assert report_response.status_code == 302
    report = ErrorReport.objects.get(opportunity=opportunity)
    assert report.description == "The deadline has changed."
    assert report.source_url == opportunity.official_source_url


@pytest.mark.django_db
@override_settings(MEILI_URL="")
def test_public_sitemap_and_robots_are_available(client) -> None:
    make_opportunity("Sitemap grant")

    sitemap_response = client.get(reverse("search:sitemap"))
    robots_response = client.get(reverse("search:robots"))

    assert sitemap_response.status_code == 200
    assert b"/opportunities/" in sitemap_response.content
    assert b"sitemap-grant" in sitemap_response.content
    assert robots_response.status_code == 200
    assert b"Sitemap: http://testserver/sitemap.xml" in robots_response.content


@pytest.mark.django_db
@override_settings(MEILI_URL="http://meilisearch.test")
def test_expiry_queues_search_reindex_for_changed_status() -> None:
    with patch("apps.search.tasks.sync_opportunity.delay") as enqueue:
        with patch(
            "apps.pipeline.services.transaction.on_commit",
            side_effect=lambda callback: callback(),
        ):
            opportunity = make_opportunity("Expired searchable grant")
            opportunity.deadline_date = timezone.localdate() - timedelta(days=1)
            opportunity.save()
            enqueue.reset_mock()
            expire_opportunities()

    opportunity.refresh_from_db()
    assert opportunity.status == Opportunity.Status.CLOSED
    enqueue.assert_called_once_with(opportunity.pk)
