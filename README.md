# GrantRadar Africa

GrantRadar Africa is a free platform for finding and tracking funding opportunities, with a focus on Africa and Nigeria. Every listing links to its official source so applicants can verify details directly.

## Status

Phase 0: repository and development-environment scaffold. Application models and grant data are not implemented yet.

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

3. Open <http://localhost:8000/>. Django admin is at <http://localhost:8000/admin/>.
4. Run checks locally with `uv sync --all-groups` followed by `make check`.

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
