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

1. A monitored source produces a candidate page.
2. A polite fetcher checks URL safety, robots.txt, rate limits, and source policy before retrieval.
3. The pipeline stores a compressed snapshot, extracts and validates opportunity facts, then normalizes and deduplicates them.
4. Extracted records remain unverified. Admins can filter low-confidence records for review and explicitly verify selected opportunities.
5. Verified records are stored in PostgreSQL; public discovery and search indexing are later phases.

The crawler must store factual fields, short original summaries, and source links—not republish full copyrighted source text. Phase 3 uses rule-based extraction only; AI extraction is deferred until a provider, budget, and validation strategy are explicitly configured.

## Phase 1 data foundation

The initial schema separates reference taxonomies, funders, opportunities, monitored sources, crawl runs, and raw snapshots. User-facing saved searches, alerts, bookmarks, pipeline items, teams, API tokens, and audit events are represented in the schema for later phases; their workflows are not active yet.

Run `python manage.py seed_reference_data` to load the offline ISO country/currency data and the starter SDG, sector, theme, and applicant-type taxonomies. Africa is pre-tagged; other countries are available for eligibility mapping and can be assigned a region in admin. Add monitored sources to `sources.yaml`, then load them with `python manage.py load_sources`.

## Phase 2 crawling

Celery Beat schedules enabled sources by their configured crawl interval. The worker starts an isolated Scrapy process per source, honors robots.txt, applies a per-domain delay and retry policy, and rejects non-public destination addresses. RSS/Atom, JSON API, CSS-configured HTML list, and sitemap adapters produce compressed, content-hashed `RawDocument` snapshots. Source runs update success time, record count, failure streak, and average yield for the admin health views. Set `CRAWLER_USER_AGENT` to a clear bot identity and contact URL before deploying.

The initial `sources.yaml` feed URLs were checked for successful HTTP responses and RSS/Atom content types on 2026-11-21. Some feeds are broader funding-announcement sources rather than grant-only feeds; all extracted opportunities remain unverified until individually reviewed.

## Phase 3 extraction and review

The pipeline extracts structured JSON API records and HTML detail pages from stored snapshots, sanitizes text, parses English, French, Portuguese, and Arabic deadlines, and declines ambiguous numeric dates. It normalizes source URLs, links fuzzy duplicates to their additional sources, assigns taxonomy tags and a confidence score, and stores new records as unverified. Admins can filter low-confidence records and explicitly verify opportunities; only verified records are automatically updated as deadlines approach or pass. AI-backed extraction is deferred.

## Phase 4 public discovery

The public home page, opportunity search/detail pages, and funder directory/detail pages use Django templates and expose only opportunities with a verification date, a non-unverified status, and an official source URL. Search filters cover country/region, sector, theme, funder, funder type, opportunity and applicant type, currency, language, status, deadline, USD amount, and matching-funds requirements. Country filters also include records with no country restrictions; these records are labeled as unrestricted rather than claiming confirmed country eligibility.

Meilisearch stores a denormalized public index. Opportunity saves and deletes queue asynchronous index updates, with bounded retries when Meilisearch is unreachable. The `reindex_opportunities` management command configures the index and rebuilds it from verified database records. Search rechecks Meilisearch hits against the database visibility and filter rules. If the service or index is unavailable, the page displays a notice and falls back to basic database keyword search.

Public pages include canonical and Open Graph metadata, `robots.txt`, and an XML sitemap. The PWA shell caches only its static stylesheet, icon, and offline page; it never caches opportunity pages that could contain stale deadlines. “Most saved” is deferred until bookmarks are implemented in Phase 5. The matching-funds field is tri-state so unknown extraction data is not presented as an explicit “no matching funds required.”

## Trust and security boundaries

- User-submitted URLs and discovered links are untrusted input. Fetchers must block private/internal addresses and re-check redirects.
- Scraped HTML must be sanitized before rendering.
- API, crawler, and notification work must have explicit timeouts, retries, and rate limits.
- Secrets are injected through environment variables; `.env` is local-only and ignored by Git.
- Opportunity details remain attributable to an official source, and users are directed to that source to verify application requirements.

## Phased implementation

The full phase plan is in `PROJECT_SPEC.md`. Phase 0 established the repository and local services. Phase 1 added the domain models, reference data, and admin workflow. Phase 2 added monitored-source crawling; Phase 3 added extraction, normalization, deduplication, and review; Phase 4 added public search and discovery pages. Later phases add accounts, alerts, bookmarks, and production hardening.
