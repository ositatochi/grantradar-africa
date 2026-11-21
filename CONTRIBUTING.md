# Contributing

Thank you for helping improve GrantRadar Africa. Contributions should make funding information more trustworthy, useful, or accessible to applicants.

## Set up the project

1. Install Python 3.12, [uv](https://docs.astral.sh/uv/), and Docker Desktop with Docker Compose.
2. Install the locked application and development dependencies:

   ```powershell
   uv sync --all-groups
   ```

3. Create a local environment file and start the services:

   ```powershell
   Copy-Item .env.example .env
   docker compose up --build
   ```

Do not use the example secrets for a public deployment. The local `.env` file is ignored by Git.

## Before opening a pull request

Run the checks that apply to your change:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy grantradar
uv run pytest
```

Keep pull requests focused. Explain the problem and the solution, add or update tests when behavior changes, and update directly related documentation. Do not include credentials, private data, or unrelated work.

## Opportunity data and crawlers

- Keep the official source URL and verification date with every opportunity.
- Prefer official APIs and feeds; follow each source's terms, `robots.txt`, and rate limits.
- Never bypass logins, paywalls, or CAPTCHAs.
- Store concise facts and original summaries rather than republishing full source text.
- Treat submitted URLs and fetched content as untrusted input. Report security or data-quality concerns clearly.
