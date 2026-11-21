# Implementation decisions

Decisions for the initial scaffold. Revisit these as the phased implementation adds actual product behavior.

| Topic | Decision | Rationale |
|---|---|---|
| Runtime | Python 3.12, managed with uv | Matches the project specification and provides reproducible dependency locking. |
| Web application | Django 5.2 with Django REST Framework | Supports the server-rendered site, administration, and versioned API in one application. |
| Database | PostgreSQL 16 with pgvector image | Provides relational storage, full-text capability, and a path to vector similarity. |
| Background services | Celery with Redis; Meilisearch as a separate service | Keeps crawling and indexing asynchronous and allows search infrastructure to evolve independently. |
| Deployment scaffold | Docker Compose for local development and a single-host deployment baseline | Gives contributors a consistent service topology; production hardening is deferred to Phase 8. |
| Initial delivery | Phase 0 contains infrastructure and documentation only | Product models, crawling, and user-facing features belong to later phases. |
| Data trust | Listings will retain official source URLs and verification dates | Applicants must be able to confirm opportunity details with the funder. |
| Crawling safety | Respect robots.txt, terms, per-domain limits, and SSRF protections | Discovery must not bypass access controls or put the service and its users at risk. |
| Project license | Undecided | Do not imply permissions for reuse or contributions until the project owner chooses a license. |
