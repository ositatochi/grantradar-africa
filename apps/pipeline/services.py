from __future__ import annotations

import gzip
import json
import logging
import re
from datetime import date, timedelta
from decimal import Decimal
from functools import partial

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError
from rapidfuzz import fuzz
from w3lib.url import canonicalize_url

from apps.accounts.models import User
from apps.core.models import ApplicantType, Country, Sector, Theme
from apps.crawler.models import RawDocument
from apps.opportunities.models import Opportunity, OpportunitySource
from apps.pipeline.extraction import confidence_score, extract_candidate, parse_deadline
from apps.pipeline.schema import OpportunityCandidate

logger = logging.getLogger(__name__)
REVIEW_CONFIDENCE_THRESHOLD = Decimal("0.750")
SECTOR_TERMS = {
    "agriculture-food-security": ("agriculture", "food security", "farming"),
    "arts-culture": ("arts", "culture"),
    "climate-environment": ("climate", "environment"),
    "economic-development": ("economic development",),
    "education-skills": ("education", "training", "skills"),
    "energy-access": ("energy", "renewable"),
    "gender-equality": ("gender", "women", "girls"),
    "governance-civil-society": ("governance", "civil society"),
    "health-nutrition": ("health", "nutrition"),
    "humanitarian-response": ("humanitarian", "emergency response"),
    "infrastructure-housing": ("infrastructure", "housing"),
    "innovation-technology": ("technology", "innovation"),
    "livelihoods-employment": ("livelihood", "employment", "jobs"),
    "peacebuilding-conflict": ("peacebuilding", "conflict"),
    "public-health": ("public health",),
    "research-science": ("research", "science"),
    "social-protection": ("social protection",),
    "water-sanitation": ("water", "sanitation"),
    "youth-development": ("youth", "young people"),
}
THEME_TERMS = {
    "climate": ("climate",),
    "disability-inclusion": ("disability", "persons with disabilities"),
    "food-security": ("food security",),
    "gender": ("gender", "women", "girls"),
    "humanitarian": ("humanitarian", "emergency response"),
    "refugees-displacement": ("refugee", "displacement"),
    "youth": ("youth", "young people"),
}


@transaction.atomic
def process_document(document_id: int) -> Opportunity | None:
    document = RawDocument.objects.select_for_update().select_related("source").get(pk=document_id)
    if document.processing_status != RawDocument.ProcessingStatus.PENDING:
        return None

    try:
        candidate = extract_candidate(document)
        if candidate is None:
            _set_document_status(
                document,
                RawDocument.ProcessingStatus.IGNORED,
                "No qualifying funding opportunity detected.",
            )
            return None
        deadline = parse_deadline(candidate.deadline_text)
        opportunity = _find_duplicate(candidate, deadline)
        if opportunity is None:
            opportunity = _create_opportunity(candidate, document, deadline)
        else:
            _merge_candidate(opportunity, candidate, deadline)
        _attach_source(opportunity, document, candidate)
        _attach_taxonomy(opportunity, candidate)
    except (
        OSError,
        EOFError,
        gzip.BadGzipFile,
        json.JSONDecodeError,
        ValueError,
        ValidationError,
        PydanticValidationError,
    ) as error:
        _set_document_status(
            document,
            RawDocument.ProcessingStatus.FAILED,
            str(error)[:1000],
        )
        logger.exception("Opportunity extraction failed", extra={"document_id": document.pk})
        return None

    _set_document_status(document, RawDocument.ProcessingStatus.PROCESSED, "")
    return opportunity


def verify_opportunity(opportunity: Opportunity, reviewer: User) -> None:
    today = timezone.localdate()
    if opportunity.rolling:
        opportunity.status = Opportunity.Status.ROLLING
    elif opportunity.deadline_date and opportunity.deadline_date < today:
        opportunity.status = Opportunity.Status.CLOSED
    elif opportunity.deadline_date and opportunity.deadline_date <= today + timedelta(days=14):
        opportunity.status = Opportunity.Status.CLOSING_SOON
    else:
        opportunity.status = Opportunity.Status.OPEN
    opportunity.date_last_verified = timezone.now()
    opportunity.verified_by = reviewer
    opportunity.full_clean()
    opportunity.save(update_fields=["status", "date_last_verified", "verified_by", "updated_at"])


def expire_opportunities() -> int:
    today = timezone.localdate()
    closing_soon_through = today + timedelta(days=14)
    verified = Opportunity.objects.exclude(status=Opportunity.Status.UNVERIFIED)
    changed_ids = list(
        verified.filter(
            Q(
                status__in=[Opportunity.Status.OPEN, Opportunity.Status.CLOSING_SOON],
                deadline_date__lt=today,
            )
            | Q(
                status=Opportunity.Status.OPEN,
                deadline_date__gte=today,
                deadline_date__lte=closing_soon_through,
            )
            | Q(
                status=Opportunity.Status.CLOSING_SOON,
                deadline_date__gt=closing_soon_through,
            )
        ).values_list("pk", flat=True)
    )
    closed = verified.filter(
        status__in=[Opportunity.Status.OPEN, Opportunity.Status.CLOSING_SOON],
        deadline_date__lt=today,
    ).update(status=Opportunity.Status.CLOSED)
    verified.filter(
        status=Opportunity.Status.OPEN,
        deadline_date__gte=today,
        deadline_date__lte=closing_soon_through,
    ).update(status=Opportunity.Status.CLOSING_SOON)
    verified.filter(
        status=Opportunity.Status.CLOSING_SOON,
        deadline_date__gt=closing_soon_through,
    ).update(status=Opportunity.Status.OPEN)
    if settings.MEILI_URL:
        from apps.search.tasks import sync_opportunity

        for opportunity_id in changed_ids:
            transaction.on_commit(partial(sync_opportunity.delay, opportunity_id))
    return closed


def _create_opportunity(
    candidate: OpportunityCandidate,
    document: RawDocument,
    deadline: date | None,
) -> Opportunity:
    opportunity = Opportunity(
        title=candidate.title,
        funder_name=candidate.funder_name,
        programme_name=candidate.programme_name,
        description_snippet=candidate.source_description[:500],
        opportunity_type=candidate.opportunity_type,
        deadline_date=deadline,
        rolling=candidate.rolling,
        official_source_url=str(candidate.official_source_url),
        source_name=document.source.name,
        date_first_found=document.fetched_at,
        confidence_score=Decimal(str(confidence_score(candidate, deadline))).quantize(
            Decimal("0.001")
        ),
        status=Opportunity.Status.UNVERIFIED,
    )
    opportunity.full_clean()
    opportunity.save()
    return opportunity


def _merge_candidate(
    opportunity: Opportunity,
    candidate: OpportunityCandidate,
    deadline: date | None,
) -> None:
    if not opportunity.funder_name and candidate.funder_name:
        opportunity.funder_name = candidate.funder_name
    if not opportunity.programme_name and candidate.programme_name:
        opportunity.programme_name = candidate.programme_name
    if not opportunity.description_snippet and candidate.source_description:
        opportunity.description_snippet = candidate.source_description[:500]
    if opportunity.deadline_date is None:
        opportunity.deadline_date = deadline
    opportunity.rolling = opportunity.rolling or candidate.rolling
    opportunity.confidence_score = max(
        opportunity.confidence_score,
        Decimal(str(confidence_score(candidate, deadline))).quantize(Decimal("0.001")),
    )
    opportunity.full_clean()
    opportunity.save(
        update_fields=[
            "funder_name",
            "programme_name",
            "description_snippet",
            "deadline_date",
            "rolling",
            "confidence_score",
            "updated_at",
        ]
    )


def _find_duplicate(
    candidate: OpportunityCandidate,
    deadline: date | None,
) -> Opportunity | None:
    canonical = canonicalize_url(str(candidate.official_source_url))
    exact_link = (
        OpportunitySource.objects.filter(canonical_url=canonical)
        .select_related("opportunity")
        .first()
    )
    if exact_link:
        return exact_link.opportunity

    tokens = [
        token for token in re.findall(r"[a-z0-9]+", candidate.title.casefold()) if len(token) > 3
    ][:4]
    if not tokens:
        return None
    title_query = Q()
    for token in tokens:
        title_query |= Q(title__icontains=token)
    candidates = Opportunity.objects.filter(title_query).order_by("-date_first_found")[:250]
    for existing in candidates:
        if fuzz.token_set_ratio(candidate.title, existing.title) < 92:
            continue
        if candidate.funder_name and existing.funder_name:
            if fuzz.token_set_ratio(candidate.funder_name, existing.funder_name) < 85:
                continue
        if deadline and existing.deadline_date:
            if abs((deadline - existing.deadline_date).days) > 30:
                continue
        return existing
    return None


def _attach_source(
    opportunity: Opportunity,
    document: RawDocument,
    candidate: OpportunityCandidate,
) -> None:
    source_url = str(candidate.official_source_url)
    canonical = canonicalize_url(source_url)
    OpportunitySource.objects.get_or_create(
        opportunity=opportunity,
        canonical_url=canonical,
        defaults={"source": document.source, "source_url": source_url},
    )


def _attach_taxonomy(opportunity: Opportunity, candidate: OpportunityCandidate) -> None:
    content = f"{candidate.title} {candidate.source_description}".casefold()
    sector_slugs = [
        slug for slug, terms in SECTOR_TERMS.items() if any(term in content for term in terms)
    ]
    theme_slugs = [
        slug for slug, terms in THEME_TERMS.items() if any(term in content for term in terms)
    ]
    applicant_slugs = []
    if re.search(r"\b(?:ngo|nonprofit|non-profit|civil society organization)\b", content):
        applicant_slugs.append("ngo")
    if re.search(r"\b(?:researcher|research institution)\b", content):
        applicant_slugs.append("researcher")
    if "university" in content:
        applicant_slugs.append("university")
    opportunity.sectors.add(*Sector.objects.filter(slug__in=sector_slugs))
    opportunity.themes.add(*Theme.objects.filter(slug__in=theme_slugs))
    opportunity.applicant_types.add(*ApplicantType.objects.filter(slug__in=applicant_slugs))

    if re.search(r"\b(?:eligible in nigeria|nigeria-based|nigerian organizations)\b", content):
        country = Country.objects.filter(alpha_2="NG").first()
        if country:
            opportunity.eligible_countries.add(country)


def _set_document_status(document: RawDocument, status: str, error: str) -> None:
    document.processing_status = status
    document.processed_at = timezone.now()
    document.processing_error = error
    document.save(update_fields=["processing_status", "processed_at", "processing_error"])
