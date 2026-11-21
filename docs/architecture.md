# Architecture

## System overview

GrantRadar Africa is a Python/Django application. Django serves the public pages and admin, while Django REST Framework exposes the future versioned API. Celery workers perform scheduled and asynchronous work. PostgreSQL is the system of record; Redis is the broker/cache; Meilisearch is the future public search index.

```text
Browser ──> Django ──> PostgreSQL
               │
               ├──> Meilisearch (search index)
               └──> Redis ──> Celery worker / Celery Beat
                                  │
                                  └──> Sources and crawler pipeline
```

The compose stack is a local-development baseline. Production deployment, secrets management, backups, observability, and security headers will be completed and tested in Phase 8.

## Repository layout

```text
grantradar/              Django project settings, URLs, ASGI/WSGI, Celery app
apps/
  accounts/               Authentication and user profiles
  analytics/              Privacy-friendly product metrics
  alerts/                 Search alerts and delivery
  api/                    Versioned REST API
  core/                   Shared utilities and health endpoint
  crawler/                Source adapters and crawl tasks
  funders/                Funder directory
  opportunities/          Opportunity records and public views
  pipeline/               Extraction, normalization, deduplication
  resources/              Grant-writing resources
  search/                 Search integration and saved queries
  sources/                Source configuration and review
  teams/                  Shared workspaces
  tracker/                Bookmarks and application pipeline
docs/                     Architecture and data model documentation
tests/                    Cross-app and integration tests
```

## Data flow

1. A monitored source or approved discovery query produces a candidate page.
2. A polite fetcher checks URL safety, robots.txt, rate limits, and source policy before retrieval.
3. The pipeline stores a compressed snapshot, extracts and validates opportunity facts, then normalizes and deduplicates them.
4. Low-confidence records enter an admin review queue. Approved records are stored in PostgreSQL and indexed in Meilisearch.
5. Public pages and the API show the official source link, last verification date, and deadline status.

The crawler must store factual fields, short original summaries, and source links—not republish full copyrighted source text. AI extraction is a fallback only and must be schema-validated, content-hash cached, and budget limited.

## Trust and security boundaries

- User-submitted URLs and discovered links are untrusted input. Fetchers must block private/internal addresses and re-check redirects.
- Scraped HTML must be sanitized before rendering.
- API, crawler, and notification work must have explicit timeouts, retries, and rate limits.
- Secrets are injected through environment variables; `.env` is local-only and ignored by Git.
- Opportunity details remain attributable to an official source, and users are directed to that source to verify application requirements.

## Phased implementation

The full phase plan is in `PROJECT_SPEC.md`. Phase 0 establishes this structure and local services; domain models and seed data begin in Phase 1. Later phases add crawling, extraction, search, accounts, alerts, and production hardening.
