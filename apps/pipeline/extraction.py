from __future__ import annotations

import gzip
import json
import re
from datetime import date
from io import BytesIO
from typing import Any

import dateparser  # type: ignore[import-untyped]
import nh3
from selectolax.parser import HTMLParser

from apps.crawler.models import RawDocument
from apps.pipeline.schema import OpportunityCandidate, OpportunityKind

MAX_DOCUMENT_BYTES = 1_000_000
FUNDING_TERMS = re.compile(
    r"\b(grant|funding|fellowship|scholarship|call for proposals|"
    r"call for applications|expression of interest|tender|award|prize|accelerator)\b",
    re.IGNORECASE,
)
DEADLINE_PATTERN = re.compile(
    r"(?:\b(?:deadline|closing date|applications close|apply by|submission deadline|"
    r"date limite|date de clôture|prazo final|data limite)\b|"
    r"(?:آخر موعد|الموعد النهائي))"
    r"\s*(?:is|on|:|-)?\s*([^\n.;]{1,60})",
    re.IGNORECASE,
)
AMBIGUOUS_NUMERIC_DATE = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$")
ROLLING_TERMS = re.compile(r"\b(rolling basis|rolling deadline|open year.round)\b", re.I)


def extract_candidate(document: RawDocument) -> OpportunityCandidate | None:
    body = _decompress(bytes(document.compressed_content))
    source_text = ""
    payload: dict[str, Any] = {}

    if "json" in document.content_type.lower():
        decoded = json.loads(body)
        if not isinstance(decoded, dict):
            return None
        payload = decoded
        source_text = _plain_text(str(payload.get("summary", "")))
    elif document.source.source_type == document.source.SourceType.HTML_DETAIL:
        page = HTMLParser(body)
        title_node = page.css_first("title")
        payload = {
            "title": title_node.text(strip=True) if title_node else "",
            "url": document.url,
        }
        source_text = _plain_text(page.text(separator=" ", strip=True))
    else:
        return None

    title = _plain_text(str(payload.get("title", "")))[:300]
    official_url = str(payload.get("url") or document.url)
    combined_text = f"{title} {source_text}"
    if not title or not FUNDING_TERMS.search(combined_text):
        return None

    deadline_match = DEADLINE_PATTERN.search(source_text)
    deadline_text = deadline_match.group(1).strip() if deadline_match else ""
    rolling = bool(ROLLING_TERMS.search(combined_text))
    opportunity_type = classify_opportunity(combined_text)

    return OpportunityCandidate.model_validate(
        {
            "title": title,
            "official_source_url": official_url,
            "opportunity_type": opportunity_type,
            "funder_name": _plain_text(str(payload.get("funder_name", "")))[:200],
            "programme_name": _plain_text(str(payload.get("programme_name", "")))[:200],
            "source_description": source_text[:4000],
            "deadline_text": deadline_text,
            "rolling": rolling,
        }
    )


def parse_deadline(value: str) -> date | None:
    value = value.strip()
    if not value or AMBIGUOUS_NUMERIC_DATE.fullmatch(value):
        return None
    parsed = dateparser.parse(
        value,
        languages=["en", "fr", "pt", "ar"],
        settings={
            "DATE_ORDER": "DMY",
            "PREFER_LOCALE_DATE_ORDER": False,
            "STRICT_PARSING": True,
        },
    )
    return parsed.date() if parsed else None


def classify_opportunity(value: str) -> OpportunityKind:
    text = value.casefold()
    if "fellowship" in text:
        return "fellowship"
    if "scholarship" in text:
        return "scholarship"
    if "tender" in text or "procurement" in text:
        return "tender"
    if "accelerator" in text:
        return "accelerator"
    if "award" in text:
        return "award"
    if "prize" in text:
        return "prize"
    if "expression of interest" in text or re.search(r"\beoi\b", text):
        return "eoi"
    if "call for proposals" in text or re.search(r"\bcall for applications\b", text):
        return "cfp"
    return "grant"


def confidence_score(
    candidate: OpportunityCandidate,
    deadline: date | None,
) -> float:
    score = 0.25
    score += 0.25 if candidate.official_source_url else 0
    score += 0.1 if FUNDING_TERMS.search(candidate.title) else 0
    score += 0.1
    score += 0.15 if deadline else 0
    score += 0.15 if candidate.funder_name else 0
    return min(score, 1.0)


def _decompress(compressed_content: bytes) -> bytes:
    with gzip.GzipFile(fileobj=BytesIO(compressed_content)) as file:
        body = file.read(MAX_DOCUMENT_BYTES + 1)
    if len(body) > MAX_DOCUMENT_BYTES:
        raise ValueError(f"Snapshot exceeds {MAX_DOCUMENT_BYTES} bytes.")
    return body


def _plain_text(value: str) -> str:
    sanitized = nh3.clean(value, tags=set(), attributes={})
    return re.sub(r"\s+", " ", HTMLParser(sanitized).text(strip=True)).strip()
