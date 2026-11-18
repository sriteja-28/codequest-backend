## code quest backend

Django 5 + DRF + Channels API for the CodeQuest platform.

**Full setup guide:** see [`../docs/README.md`](../docs/README.md).
**API reference:** [`../docs/api.md`](../docs/api.md).
**Environment variables:** [`.env.example`](.env.example) — every variable is annotated; production requirements are marked `[PROD-REQUIRED]`.

Quick reference:

```bash
python -m venv leet_venv && leet_venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_data          # dev seeds; refuses without DEBUG=true (--force to override)
uvicorn config.asgi:application --port 8000
```

Settings modules: `config.settings.development` (default, Redis auto-fallback), `config.settings.production` (fail-fast), `config.settings.test` (pinned by pytest.ini).

Operational commands:

- `python manage.py reap_stuck_submissions` — mark QUEUED/RUNNING submissions older than `JUDGE_STALE_SUBMISSION_SECONDS` as INTERNAL_ERROR (also runs automatically on submission reads).
- `python manage.py recalculate_stats` — rebuild denormalized counters (user solved/streak, problem submission stats) after data imports or manual fixes.

The judge worker (../judge) calls back through `X-Judge-Api-Key` internal routes — deploy backend and judge together when upgrading.
