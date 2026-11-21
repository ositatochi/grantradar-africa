# GrantRadar Africa

GrantRadar Africa is a free platform for finding and tracking funding opportunities, with a focus on Africa and Nigeria. Every listing links to its official source so applicants can verify details directly.

## Status

Phase 5 is implemented: people can register with email, optionally sign in with configured Google OAuth, personalize recommendations, save searches, opt into email alerts and deadline reminders, bookmark opportunities, track applications with private notes, and export pipeline deadlines to a calendar. Phase 4 public discovery remains restricted to verified opportunities with official source links. Email verification is required for new email accounts.

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
   Local email is printed to the Django container console. Configure SMTP and the optional Google OAuth client in `.env` before enabling those services outside local development.
6. To load sources configured in `sources.yaml`, run:

   ```powershell
   docker compose exec django uv run python manage.py load_sources
   ```

7. For local Playwright-backed sources, install Chromium with `uv run playwright install chromium`.
8. Run checks locally with `uv sync --all-groups` followed by `make check`. Pytest uses an in-memory SQLite database; the application and Compose stack use PostgreSQL.
9. After configuring `MEILI_URL` and `MEILI_MASTER_KEY`, build or refresh the public search index with:

   ```powershell
   docker compose exec django uv run python manage.py reindex_opportunities
   ```

Celery Beat schedules enabled source crawls every 15 minutes; the configured crawl frequency determines which sources are due. To enable the separate Playwright worker for JavaScript-rendered sources:

```powershell
docker compose --profile crawler up --build
```

The optional Celery Flower dashboard is available with:

```powershell
docker compose --profile monitoring up --build
```

Email alerts run every 15 minutes, and opted-in application deadline reminders run daily for deadlines 14, 7, 3, and 1 day away. Set `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL` for SMTP. Google sign-in is shown only when both `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are set.

## Project documentation

- [Project specification](./PROJECT_SPEC.md)
- [Architecture](./docs/architecture.md)
- [Data model / ERD](./docs/erd.md)
- [Implementation decisions](./DECISIONS.md)

## Contribution workflow

Work in small, reviewable branches. Open a pull request with tests and a clear description; merge it only after review and CI pass. GitHub achievement badges are awarded by GitHub based on qualifying contribution activity and cannot be granted by this application.
