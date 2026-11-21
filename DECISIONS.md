# Implementation decisions

Decisions for the initial scaffold. Revisit these as the phased implementation adds actual product behavior.

| Topic | Decision | Rationale |
|---|---|---|
| Runtime | Python 3.12, managed with uv | Matches the project specification and provides reproducible dependency locking. |
| Web application | Django 5.2 with Django REST Framework | Supports the server-rendered site, administration, and versioned API in one application. |
| Database | PostgreSQL 16 with pgvector image | Provides relational storage, full-text capability, and a path to vector similarity. |
| Background services | Celery with Redis; Meilisearch as a separate service | Keeps crawling and indexing asynchronous and allows search infrastructure to evolve independently. |
| User model | Define a minimal custom Django user model in Phase 1 | Selected before the first migration to avoid a disruptive user-model swap later; profile features remain deferred. |
| Test database | Use in-memory SQLite for pytest; keep PostgreSQL for application/deployment environments | Allows deterministic model and migration tests without requiring Docker or a local PostgreSQL service. |
| Country and currency reference data | Seed from the offline ISO dataset bundled with `pycountry` | Provides broad country/currency coverage without runtime network access. |
| Country regions | Pre-tag recognized African countries as `Africa`; leave other region values blank | Avoids inventing subregions before a geographic taxonomy is chosen while keeping all countries selectable. |
| Deployment scaffold | Docker Compose for local development and a single-host deployment baseline | Gives contributors a consistent service topology; production hardening is deferred to Phase 8. |
| Phase 1 delivery | Migrations, seed commands, and source/opportunity admin are implemented; crawl and user workflows remain deferred | Keeps the data foundation usable without prematurely implementing later discovery phases. |
| Data trust | Listings will retain official source URLs and verification dates | Applicants must be able to confirm opportunity details with the funder. |
| Crawling safety | Respect robots.txt, terms, per-domain limits, and SSRF protections | Discovery must not bypass access controls or put the service and its users at risk. |
| Project license | Undecided | Do not imply permissions for reuse or contributions until the project owner chooses a license. |
