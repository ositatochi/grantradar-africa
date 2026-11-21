# Implementation decisions

Implementation decisions for the phased project. Revisit these as product behavior evolves.

| Topic | Decision | Rationale |
|---|---|---|
| Runtime | Python 3.12, managed with uv | Matches the project specification and provides reproducible dependency locking. |
| Web application | Django 5.2 with Django REST Framework | Supports the server-rendered site, administration, and versioned API in one application. |
| Database | PostgreSQL 16 with pgvector image | Provides relational storage, full-text capability, and a path to vector similarity. |
| Background services | Celery with Redis; Meilisearch as a separate service | Keeps crawling and indexing asynchronous and allows search infrastructure to evolve independently. |
| User model | Extend the custom Django user with unique email and profile preferences | The model was selected before the first migration; keeping profile preferences on it avoids a disruptive user-model swap. |
| Test database | Use in-memory SQLite for pytest; keep PostgreSQL for application/deployment environments | Allows deterministic model and migration tests without requiring Docker or a local PostgreSQL service. |
| Country and currency reference data | Seed from the offline ISO dataset bundled with `pycountry` | Provides broad country/currency coverage without runtime network access. |
| Country regions | Pre-tag recognized African countries as `Africa`; leave other region values blank | Avoids inventing subregions before a geographic taxonomy is chosen while keeping all countries selectable. |
| Deployment scaffold | Docker Compose for local development and a single-host deployment baseline | Gives contributors a consistent service topology; production hardening is deferred to Phase 8. |
| Phase 1 delivery | Migrations, seed commands, and source/opportunity admin were implemented before crawl and user workflows | Keeps the data foundation usable without prematurely implementing later discovery phases. |
| Phase 2 crawler runtime | Run each Scrapy source crawl in a child process from Celery | Avoids restarting Twisted's reactor in long-lived Celery workers while keeping crawl failures isolated per source. |
| Initial crawl sources | Seed ten live RSS/Atom feeds first; defer blocked or mislabelled feed endpoints until their official APIs are verified | The candidate Grants.gov `.xml` URL returned an HTML application page, so it is not treated as a working feed. |
| Data trust | Listings will retain official source URLs and verification dates | Applicants must be able to confirm opportunity details with the funder. |
| Crawling safety | Respect robots.txt, terms, per-domain limits, and SSRF protections | Discovery must not bypass access controls or put the service and its users at risk. |
| Phase 3 extraction | Use schema-validated rule-based extraction; keep extracted opportunities unverified until an admin explicitly reviews them | No AI provider or credentials are configured. This avoids unreviewed claims while leaving AI extraction for a later, budgeted decision. |
| Public visibility | Require a verification timestamp, a verified status, and an official source URL before indexing or displaying an opportunity | Search indexes can lag behind database changes, so public requests recheck eligibility against the database. |
| Phase 4 search fallback | Use Meilisearch for full-text search and fall back to database keyword matching with a visible notice when it is not configured or available | Public discovery remains usable during local development or a search-service outage without hiding the degraded search behavior. |
| Unknown matching-funds requirement | Store the field as nullable; unknown is distinct from an explicit “not required” value | Existing records defaulted to false without extraction evidence, so they are migrated to unknown to avoid misleading applicants. |
| Public site assets | Use server-rendered Django templates and a small first-party CSS/PWA shell without a frontend build dependency | The repository had no frontend asset pipeline, and a small static asset set keeps the public site lightweight and easy to run. |
| Account authentication | Use django-allauth for email login with mandatory email verification; enable Google only when both OAuth credentials are present | Unverified addresses should not receive private alerts, and local development must not display a nonfunctional Google sign-in link. |
| Search-alert consent | Require and timestamp explicit consent before an email alert can be active; keep Telegram and WhatsApp inactive until their integrations are implemented | Notification preferences must be auditable and the UI must not promise channels that cannot deliver. |
| Deadline reminders | Require a separate user opt-in and send reminders only for active public pipeline opportunities | Saved-search alert consent should not imply consent to a different notification purpose. |
| Saved-opportunity metrics | Show “most saved” only from real bookmark counts | The popularity section must reflect actual user activity rather than a placeholder or fabricated ranking. |
| Personal tracker privacy | Owner-scope bookmarks, pipeline items, notes, and ICS exports | Application progress and notes may be sensitive to the user and must not be exposed across accounts. |
| Project license | Undecided | Do not imply permissions for reuse or contributions until the project owner chooses a license. |
