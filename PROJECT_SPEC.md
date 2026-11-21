ROLE
You are a senior full-stack and data engineer. Build "GrantRadar Africa": a free, robust web platform that continuously discovers, extracts, cleans and serves grant and funding opportunities for ALL development sectors, with focus on Africa and Nigeria. It serves grant writers, NGOs, CBOs, researchers and social enterprises in Nigeria. Users open the original link to verify details themselves, so every record MUST carry the official source link.

The whole project is Python. Work in phases. At the start of each phase, state your plan in a short list, then implement, run tests, and summarise what is done. Do not skip phases. Ask me only when a decision is truly blocking; otherwise choose sensible defaults and document them in DECISIONS.md.

1. TECH STACK (all Python; change only with a strong reason)
- Language and runtime: Python 3.12, managed with uv or Poetry.
- Web framework: Django 5 with Django REST Framework (API), django-allauth (email + Google login), django-filter, drf-spectacular (OpenAPI docs).
- Admin: Django admin customised with django-unfold (modern UI) for sources, review queue, taxonomy, users, monitoring.
- Front end: Django templates + HTMX + Alpine.js + Tailwind CSS. Server-rendered, mobile-first, lightweight for low-bandwidth networks. PWA (manifest + service worker).
- Background jobs and scheduling: Celery 5 + Redis, Celery Beat (django-celery-beat so schedules are editable in admin), Flower for monitoring.
- Crawler: Scrapy (large crawls, politeness, retries) + Playwright (scrapy-playwright) for JavaScript-heavy pages; httpx for APIs; feedparser for RSS; trafilatura and selectolax for content extraction; dateparser for dates; tldextract and w3lib for URL handling. Crawler code lives in the same repo as a Django app (crawler/) and writes through Django models.
- Database: PostgreSQL 16 with pg_trgm and full-text search; pgvector for embeddings.
- Search: Meilisearch (typo-tolerant, fast facets) using meilisearch-python, indexed from Celery tasks.
- AI extraction: provider-agnostic adapter (Anthropic Claude or OpenAI via settings), used ONLY as a fallback for messy pages. Validate output with Pydantic against a strict schema. Cache by content hash so the same page is never paid for twice. Daily budget cap.
- Email: Django + Anymail (Brevo, Mailgun or Resend). Telegram bot via python-telegram-bot. WhatsApp via the WhatsApp Business Cloud API.
- Deployment: Docker Compose (django/gunicorn, nginx or Caddy, postgres, redis, meilisearch, celery-worker, celery-beat, flower, playwright-worker). Target one 4 GB VPS. Include .env.example, Makefile, README with one-command setup.
- Quality: pytest + pytest-django + factory_boy, Ruff (lint + format), mypy, pre-commit, GitHub Actions CI, Sentry SDK for errors, structlog for logging, django-debug-toolbar in dev.

2. DISCOVERY ENGINE (both methods required)
A) Monitored sources: a Source model with type (api, rss, html_list, html_detail, sitemap, newsletter_email), URL, crawl frequency, adapter class or CSS/XPath selectors, country/sector tags, reliability score, enabled flag. Build a pluggable adapter system: one small adapter class per source; a generic configurable adapter handles simple sites with no code.
B) Web-search discovery: scheduled saved queries run through a search API (Serper, Brave or Tavily, configurable). Maintain a query library by sector x region x grant type x year, e.g. "call for proposals {sector} Nigeria {year}", "request for applications Africa {sector}", "fellowship grant African {sector} deadline". New domains found this way go into a CandidateSource review queue in admin with a one-click "promote to monitored source". Zero-result user searches automatically suggest new queries.
Also support: email newsletter ingestion (IMAP mailbox), and manual URL submission (paste a link, the system extracts it).

Seed sources (verify each is live; research and propose at least 40 more, especially Nigeria- and Africa-specific): Funds for NGOs, Opportunity Desk, Devex, Grants.gov, EU Funding & Tenders Portal, UNDP, UN Women, UNICEF, UNFPA, FAO, World Bank, African Development Bank, African Union, GIZ, UK FCDO/UKRI, Gates Foundation, Ford Foundation, MacArthur, Open Society, Wellcome, Mastercard Foundation, Tony Elumelu Foundation, Segal Family Foundation, TrustAfrica, Africa Grantmakers' Affinity Group, Global Fund for Community Foundations, GlobalGiving, Skoll, Echoing Green, Aga Khan Foundation, Hewlett Foundation, Rockefeller Foundation, Google.org, Meta/Microsoft/Mozilla grants, embassy small-grant programmes in Nigeria, Nigerian foundations and agencies. Keep them in sources.yaml loaded by a management command (python manage.py load_sources), not hardcoded.

3. CRAWLING RULES AND ROBUSTNESS
- Respect robots.txt, per-domain rate limits and site terms. Clear User-Agent with contact URL. Never bypass logins, paywalls or CAPTCHAs.
- Prefer APIs and feeds over scraping. Store facts, short summaries and the link; never republish full copyrighted text.
- Retries with exponential backoff, per-domain circuit breaker, timeouts, dead-letter handling, idempotent Celery tasks.
- Change detection using content hashes and ETag/Last-Modified; reprocess only changed pages.
- Store compressed raw snapshots (HTML/JSON) so records can be re-extracted later.
- Source health dashboard: last success, last count, failure streak, average yield; alert admin by email/Telegram when a source returns zero or errors repeatedly.
- SSRF protection (block internal/private IPs), sanitise all scraped HTML (nh3 or bleach).
- Structured logs, Sentry, and metrics: pages crawled, records created, extraction cost, queue depth.

4. EXTRACTION AND CLEANING PIPELINE
Pipeline: fetch -> clean text -> rule-based extraction -> (if low confidence) LLM extraction -> Pydantic validation -> normalise -> deduplicate -> classify -> score -> index in Meilisearch.
Fields per opportunity: title, funder name, funder type (foundation, government, multilateral, corporate, embassy, bank, university, other), programme name, summary (max 120 words, our own words), description snippet, opportunity type (grant, fellowship, award, prize, scholarship, tender/contract, accelerator, call for expressions of interest, call for proposals), amount min/max, currency, amount in USD and NGN (daily exchange rates), deadline (date, time, timezone, rolling flag), open date, eligible countries and regions, excluded countries, applicant types (NGO, CBO, FBO, individual, researcher, startup/SME, government, university), sectors (controlled taxonomy aligned with UN SDGs plus sub-sectors), themes (gender, youth, disability, climate, humanitarian, etc.), co-funding or matching required, eligibility notes, how to apply, application link, official source URL, source name, language, date first found, date last verified, confidence score, status (open, closing soon, closed, rolling, upcoming, unverified).
- Dates: parse many formats and languages (English, French, Portuguese, Arabic) with dateparser; handle timezones; flag ambiguity instead of guessing.
- Deduplication: canonical URLs, fuzzy matching (rapidfuzz on title + funder + deadline), and pgvector embedding similarity; merge duplicates and keep every source link as "also seen on".
- Auto-expire closed calls after the deadline; keep them in an archive (past calls predict recurring annual grants).
- Detect recurring programmes and show "likely to reopen around {month}".
- Confidence score and a human review queue in admin for low-confidence records.

5. USER-FACING FEATURES (build all)
Discovery and search:
- Home page with "New today", "Closing soon (7/14/30 days)", "Open to Nigeria", "Africa-wide", "Rolling", "Most saved".
- Full-text, typo-tolerant search with facets and filters: country, region, sector/SDG, theme, funder, funder type, opportunity type, applicant type, amount range, currency, deadline range, language, status, "eligible for Nigerian organisations", "no matching funds required", "individuals allowed".
- Sort by deadline, newest, amount, relevance, best match.
- Opportunity detail page: all fields, official link prominent, "also seen on" links, last-verified date, report-an-error button, similar opportunities, funder profile.
- Funder directory: past and current calls, typical amounts, sectors, countries, deadline patterns.
- Calendar view of deadlines; browse by country and sector.
Accounts and personalisation:
- Sign up by email or Google; profile with organisation type, sectors, countries, budget range.
- "Best match" scoring from profile and behaviour.
- Saved searches with alerts by email, WhatsApp and Telegram; instant, daily or weekly digests; RSS and JSON feed per search.
- Bookmarks, pipeline tracker (Interested, Preparing, Submitted, Awarded, Rejected), private notes, checklists, reminders at 14/7/3/1 days, ICS and Google Calendar export.
- Team workspaces: shared pipelines, assignments, comments.
- Export to CSV, Excel and PDF; shareable link of a filtered list.
Helpful extras for grant writers:
- Plain-language "eligibility quick check": what they fund / what they don't.
- Links to guidelines, templates and FAQs; a checklist of required attachments.
- Optional AI helper: summarise guidelines, extract evaluation criteria, draft a requirements checklist (labelled AI-generated, always linking to the source).
- Funder intelligence: average grant size, language and format requirements.
- Resource library: proposal-writing guides, logframes, budgets, donor formats, glossary.
- Community: moderated user-submitted opportunities, error reports, upvotes, "I applied" counts.
- Accessibility (WCAG AA), dark mode, multilingual interface (English first; French, Hausa, Yoruba, Igbo later).
Admin:
- Manage sources, adapters, queries, candidate sources, review queue, users, taxonomy, funders, announcements, feature flags.
- Crawl monitor, LLM and search API cost monitor, manual re-crawl, bulk edit, merge duplicates, domain blacklist.
- Privacy-friendly analytics: top searches, popular sectors, zero-result searches.
Public API:
- Versioned REST API (/api/v1) with token auth, throttling, filters, pagination and OpenAPI docs.

6. DATA MODEL
Design and migrate models for: Source, SourceRun, RawDocument, Opportunity, OpportunitySource, Funder, Sector, Country, ApplicantType, SavedSearch, Alert, AlertDelivery, Bookmark, PipelineItem, Note, Team, TeamMember, Comment, SearchQuery, CandidateSource, ErrorReport, APIToken, AuditLog. Add indexes, foreign keys, constraints and fixtures/seed commands for countries, SDGs, sectors and currencies. Provide an ERD in docs/.

7. SECURITY, PRIVACY, COMPLIANCE
- Comply with the Nigeria Data Protection Act 2023: privacy policy, consent for alerts, data minimisation, user data export and deletion, breach procedure, record of processing.
- Django security settings hardened (HTTPS, HSTS, secure cookies, CSP), rate limiting (django-ratelimit), 2FA for admins (django-otp), encrypted secrets via environment variables, least-privilege DB users.
- Daily encrypted database backups with a tested restore procedure; uptime monitoring.

8. PERFORMANCE AND COST CONTROL
- Cache hot pages (Redis), queue everything slow, paginate everywhere, serve search from Meilisearch, put Cloudflare (free tier) in front.
- LLM budget cap per day with fallback to rule-based extraction; log cost per record.

9. PROJECT STRUCTURE
grantradar/ (Django project), apps: core, accounts, sources, crawler, pipeline (extraction/dedupe/classify), opportunities, funders, search, alerts, tracker, teams, api, resources, analytics. Plus docker/, docs/, tests/, sources.yaml, Makefile.

10. BUILD PHASES (stop and summarise after each)
Phase 0: Repo scaffold, Docker Compose, CI, pre-commit, DECISIONS.md, ERD and architecture doc.
Phase 1: Models, migrations, seed data, taxonomy, Django admin for sources and opportunities.
Phase 2: Scrapy/Playwright crawler with adapters for 10 high-quality sources (APIs and RSS first), snapshots, Celery tasks, health logging.
Phase 3: Extraction, normalisation, deduplication, expiry, confidence scoring, review queue.
Phase 4: Meilisearch, public site (home, search, filters, detail, funder pages), SEO, PWA.
Phase 5: Accounts, saved searches, alerts (email first, then Telegram and WhatsApp), bookmarks, pipeline tracker, calendar export.
Phase 6: Web-search discovery engine, candidate-source review, scale to 50+ sources, recurring-call prediction.
Phase 7: Teams, public API, AI helper, resource library, multilingual interface, analytics.
Phase 8: Hardening, load tests, backups, monitoring, documentation, launch checklist.

11. DEFINITION OF DONE
- Every opportunity shown has an official link, a last-verified date and a deadline status.
- At least 50 working sources; yield and failure report visible in admin.
- Zero duplicates in a 500-record audit; at least 90 percent of records have a correct deadline.
- Tests cover parsers, dedupe, date handling and alerts; CI green.
- README lets a new developer run everything with one command.

Begin with Phase 0 now. Create the folder structure, docker-compose.yml, .env.example, pyproject.toml, README skeleton, DECISIONS.md and docs/architecture.md, then wait for my "continue" before Phase 1.
