from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.core.models import (
    ApplicantType,
    Country,
    Currency,
    Sector,
    SustainableDevelopmentGoal,
    Theme,
)
from apps.opportunities.admin import OpportunityAdmin
from apps.opportunities.models import Opportunity
from apps.sources.admin import SourceAdmin
from apps.sources.models import Source


@pytest.mark.django_db
def test_reference_data_command_is_repeatable() -> None:
    call_command("seed_reference_data")
    first_counts = (
        Country.objects.count(),
        Currency.objects.count(),
        SustainableDevelopmentGoal.objects.count(),
        Sector.objects.count(),
        Theme.objects.count(),
        ApplicantType.objects.count(),
    )

    call_command("seed_reference_data")

    assert first_counts == (
        Country.objects.count(),
        Currency.objects.count(),
        SustainableDevelopmentGoal.objects.count(),
        Sector.objects.count(),
        Theme.objects.count(),
        ApplicantType.objects.count(),
    )
    assert first_counts[0] >= 200
    assert first_counts[2] == 17
    assert Country.objects.get(alpha_2="NG").region == "Africa"
    assert Currency.objects.get(code="USD").is_active is True


@pytest.mark.django_db
def test_source_loader_creates_and_updates_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    call_command("seed_reference_data")
    source_file = tmp_path / "sources.yaml"
    source_data = {
        "sources": [
            {
                "name": "Example RSS",
                "source_type": "rss",
                "url": "https://example.org/feed.xml",
                "countries": ["NG"],
                "sectors": ["agriculture-food-security"],
            }
        ]
    }
    source_file.write_text(yaml.safe_dump(source_data), encoding="utf-8")
    monkeypatch.setattr(
        "apps.sources.management.commands.load_sources.SOURCE_FILE",
        source_file,
    )

    call_command("load_sources")
    call_command("load_sources")

    source = Source.objects.get(url="https://example.org/feed.xml")
    assert Source.objects.count() == 1
    assert list(source.countries.values_list("alpha_2", flat=True)) == ["NG"]
    assert list(source.sectors.values_list("slug", flat=True)) == ["agriculture-food-security"]


@pytest.mark.django_db
def test_source_and_opportunity_are_registered_in_admin() -> None:
    assert isinstance(admin.site._registry[Source], SourceAdmin)
    assert isinstance(admin.site._registry[Opportunity], OpportunityAdmin)


def test_opportunity_rejects_summary_over_120_words() -> None:
    opportunity = Opportunity(
        title="Example opportunity",
        opportunity_type=Opportunity.OpportunityType.GRANT,
        official_source_url="https://example.org/grant",
        summary=" ".join(["word"] * 121),
    )

    with pytest.raises(ValidationError, match="120 words"):
        opportunity.clean()


def test_opportunity_rejects_deadline_before_open_date() -> None:
    opportunity = Opportunity(
        title="Example opportunity",
        opportunity_type=Opportunity.OpportunityType.GRANT,
        official_source_url="https://example.org/grant",
        open_date=date(2026, 6, 1),
        deadline_date=date(2026, 5, 1),
    )

    with pytest.raises(ValidationError, match="Deadline cannot be before"):
        opportunity.clean()


def test_opportunity_rejects_unknown_deadline_timezone() -> None:
    opportunity = Opportunity(
        title="Example opportunity",
        opportunity_type=Opportunity.OpportunityType.GRANT,
        official_source_url="https://example.org/grant",
        deadline_timezone="Not/A_Timezone",
    )

    with pytest.raises(ValidationError, match="valid IANA timezone"):
        opportunity.clean()


@pytest.mark.django_db
def test_opportunity_amount_range_database_constraint() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Opportunity.objects.create(
            title="Invalid amount range",
            opportunity_type=Opportunity.OpportunityType.GRANT,
            official_source_url="https://example.org/grant",
            amount_min=Decimal("1000.00"),
            amount_max=Decimal("500.00"),
        )


@pytest.mark.django_db
def test_verified_opportunity_requires_verification_date() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Opportunity.objects.create(
            title="Unverified open opportunity",
            opportunity_type=Opportunity.OpportunityType.GRANT,
            official_source_url="https://example.org/grant",
            status=Opportunity.Status.OPEN,
        )
