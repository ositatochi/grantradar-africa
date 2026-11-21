# GrantRadar Africa

GrantRadar Africa is a free platform for finding and tracking funding opportunities, with a focus on Africa and Nigeria. Every listing links to its official source so applicants can verify details directly.

## Status

Phase 3 is complete: scheduled source crawls store compressed snapshots, and a rule-based pipeline extracts and normalizes opportunities, deduplicates records, scores confidence, and tracks review and expiry. Extracted opportunities remain unverified until an admin explicitly verifies them. Public discovery is the next phase.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop with Docker Compose

## Local development

1. Copy `.env.example` to `.env` and replace the example secrets for any non-local use.
2. Start the services:

   ```powershell
   docker compose up --build
   ```

3. Seed countries, currencies, SDGs, and taxonomies:

   ```powershell
   docker compose exec django uv run python manage.py seed_reference_data
   ```

4. Create an admin account:

   ```powershell
   docker compose exec django uv run python manage.py createsuperuser
   ```

5. Open <http://localhost:8000/>. Django admin is at <http://localhost:8000/admin/>.
6. To load sources configured in `sources.yaml`, run:

   ```powershell
   docker compose exec django uv run python manage.py load_sources
   ```

7. For local Playwright-backed sources, install Chromium with `uv run playwright install chromium`.
8. Run checks locally with `uv sync --all-groups` followed by `make check`. Pytest uses an in-memory SQLite database; the application and Compose stack use PostgreSQL.

Celery Beat schedules enabled source crawls every 15 minutes; the configured crawl frequency determines which sources are due. To enable the separate Playwright worker for JavaScript-rendered sources:

```powershell
docker compose --profile crawler up --build
```

The optional Celery Flower dashboard is available with:

```powershell
docker compose --profile monitoring up --build
```

## Project documentation

- [Project specification](./PROJECT_SPEC.md)
- [Architecture](./docs/architecture.md)
- [Data model / ERD](./docs/erd.md)
- [Implementation decisions](./DECISIONS.md)

## Contribution workflow

Work in small, reviewable branches. Open a pull request with tests and a clear description; merge it only after review and CI pass. GitHub achievement badges are awarded by GitHub based on qualifying contribution activity and cannot be granted by this application.
