from __future__ import annotations

import gzip
import hashlib
import json
from datetime import date, timedelta

import pytest
from django.contrib.auth.models import AbstractUser
from django.core.management import call_command
from django.utils import timezone

from apps.crawler.models import RawDocument, SourceRun
from apps.opportunities.models import Opportunity, OpportunitySource
from apps.pipeline.extraction import extract_candidate, parse_deadline
from apps.pipeline.services import expire_opportunities, process_document, verify_opportunity
from apps.sources.models import Source


def make_document(
    source: Source,
    title: str,
    summary: str,
    url: str = "https://example.org/call",
) -> RawDocument:
    content = json.dumps({"title": title, "url": url, "summary": summary}).encode()
    return RawDocument(
        source=source,
        url=url,
        canonical_url=url,
        content_type="application/json",
        content_hash=hashlib.sha256(content).hexdigest(),
        compressed_content=gzip.compress(content),
    )


def test_extraction_classifies_and_parses_explicit_deadline() -> None:
    source = Source(source_type=Source.SourceType.RSS)
    document = make_document(
        source,
        "Agriculture grant for NGOs",
        "<p>Apply by 30 June 2027. Eligible for Nigeria-based NGOs.</p>",
    )

    candidate = extract_candidate(document)

    assert candidate is not None
    assert candidate.opportunity_type == "grant"
    assert candidate.deadline_text == "30 June 2027"
    assert parse_deadline(candidate.deadline_text) == date(2027, 6, 30)


def test_ambiguous_numeric_deadline_is_not_guessed() -> None:
    assert parse_deadline("05/06/2027") is None
    assert parse_deadline("31 May 2027") == date(2027, 5, 31)


@pytest.mark.parametrize(
    ("deadline_text", "expected"),
    [
        ("30 June 2027", date(2027, 6, 30)),
        ("30 juin 2027", date(2027, 6, 30)),
        ("30 de junho de 2027", date(2027, 6, 30)),
        ("30 يونيو 2027", date(2027, 6, 30)),
    ],
)
def test_deadline_parsing_supports_project_languages(
    deadline_text: str,
    expected: date,
) -> None:
    assert parse_deadline(deadline_text) == expected


@pytest.mark.django_db
def test_processing_creates_unverified_opportunity_and_source_link() -> None:
    call_command("seed_reference_data")
    source = Source.objects.create(
        name="Example RSS",
        source_type=Source.SourceType.RSS,
        url="https://example.org/feed",
    )
    run = SourceRun.objects.create(source=source, status=SourceRun.Status.SUCCEEDED)
    document = make_document(
        source,
        "Agriculture grant for NGOs",
        "Apply by 30 June 2027. Eligible for Nigeria-based NGOs.",
    )
    document.source_run = run
    document.save()

    opportunity = process_document(document.pk)

    assert opportunity is not None
    assert opportunity.status == Opportunity.Status.UNVERIFIED
    assert opportunity.date_last_verified is None
    assert opportunity.deadline_date == date(2027, 6, 30)
    assert opportunity.eligible_countries.get().alpha_2 == "NG"
    assert opportunity.sectors.filter(slug="agriculture-food-security").exists()
    assert OpportunitySource.objects.filter(
        opportunity=opportunity,
        source=source,
        canonical_url="https://example.org/call",
    ).exists()
    document.refresh_from_db()
    assert document.processing_status == RawDocument.ProcessingStatus.PROCESSED


@pytest.mark.django_db
def test_fuzzy_duplicate_keeps_both_source_links() -> None:
    first_source = Source.objects.create(
        name="First feed",
        source_type=Source.SourceType.RSS,
        url="https://first.example.org/feed",
    )
    second_source = Source.objects.create(
        name="Second feed",
        source_type=Source.SourceType.RSS,
        url="https://second.example.org/feed",
    )
    first = make_document(
        first_source,
        "Women in Agriculture Grant 2027",
        "Deadline: 30 June 2027.",
    )
    first.save()
    second = make_document(
        second_source,
        "Women Agriculture Grant Program 2027",
        "Deadline: 30 June 2027.",
        "https://second.example.org/call",
    )
    second.save()

    first_opportunity = process_document(first.pk)
    second_opportunity = process_document(second.pk)

    assert first_opportunity is not None
    assert second_opportunity is not None
    assert first_opportunity.pk == second_opportunity.pk
    assert Opportunity.objects.count() == 1
    assert OpportunitySource.objects.filter(opportunity=first_opportunity).count() == 2


@pytest.mark.django_db
def test_expiry_closes_verified_records_only() -> None:
    past_deadline = timezone.localdate() - timedelta(days=1)
    verified = Opportunity.objects.create(
        title="Verified grant",
        opportunity_type=Opportunity.OpportunityType.GRANT,
        official_source_url="https://example.org/verified",
        deadline_date=past_deadline,
        date_last_verified=timezone.now(),
        status=Opportunity.Status.OPEN,
    )
    unverified = Opportunity.objects.create(
        title="Unverified grant",
        opportunity_type=Opportunity.OpportunityType.GRANT,
        official_source_url="https://example.org/unverified",
        deadline_date=past_deadline,
        status=Opportunity.Status.UNVERIFIED,
    )

    assert expire_opportunities() == 1

    verified.refresh_from_db()
    unverified.refresh_from_db()
    assert verified.status == Opportunity.Status.CLOSED
    assert unverified.status == Opportunity.Status.UNVERIFIED


@pytest.mark.django_db
def test_manual_verification_records_reviewer_and_status(
    django_user_model: type[AbstractUser],
) -> None:
    reviewer = django_user_model.objects.create_user(username="reviewer", password="unused")
    opportunity = Opportunity.objects.create(
        title="Grant closing soon",
        opportunity_type=Opportunity.OpportunityType.GRANT,
        official_source_url="https://example.org/verify",
        deadline_date=timezone.localdate() + timedelta(days=3),
        status=Opportunity.Status.UNVERIFIED,
    )

    verify_opportunity(opportunity, reviewer)

    opportunity.refresh_from_db()
    assert opportunity.status == Opportunity.Status.CLOSING_SOON
    assert opportunity.date_last_verified is not None
    assert opportunity.verified_by == reviewer
