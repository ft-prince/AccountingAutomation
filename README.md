# Nexren Finance

GST invoice automation, client email assistant, financial reporting and cashflow
forecasting for Nexren AI / Renata IoT. Django REST API + Next.js. The full
specification is in [PROJECT_SPECS.md](PROJECT_SPECS.md); engineering rules in
[CLAUDE.md](CLAUDE.md).

## Setup

```bash
cp .env.example .env            # fill in secrets; blank values fall back to dev defaults
docker compose up -d --build    # postgres, redis, minio, backend, worker, beat, frontend
docker compose exec backend python manage.py generate_demo_data
open http://localhost:3000      # login: demo@nexren.ai / demo1234
```

- API docs: http://localhost:8000/api/docs/ (dev only)
- Health: http://localhost:8000/api/health
- MinIO console: http://localhost:9001 (minioadmin / minioadmin)

Local development without Docker: `cd backend && uv sync --group dev` then
`.venv/bin/python manage.py runserver`; `cd frontend && npm i --legacy-peer-deps && npm run dev`.

## Tests

```bash
make test        # backend pytest + frontend vitest
make lint        # ruff, mypy, eslint
cd backend && .venv/bin/pytest apps/gst --cov=apps.gst.domain --cov-branch --cov-fail-under=100
cd backend && .venv/bin/pytest -m live   # opt-in: real Anthropic call, needs ANTHROPIC_API_KEY
```

CI (`.github/workflows/ci.yml`) runs ruff, mypy, pytest with an 80% gate and a
100% branch gate on every `domain/` package, plus the send-call-site grep test,
then `npm run lint && npm test && npm run build`.

## Deploy

Images: `backend/Dockerfile.prod` (gunicorn, non-root, no dev deps) and
`frontend/Dockerfile.prod` (Next standalone). Required env in production:
`DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL`, `S3_*`,
`ANTHROPIC_API_KEY`, `FIELD_ENCRYPTION_KEY`, OAuth client ids/secrets,
`CSRF_TRUSTED_ORIGINS`, optional `SENTRY_DSN`. `DJANGO_SETTINGS_MODULE=config.settings.prod`
turns on HSTS, secure cookies, S3 storage and JSON logs with `X-Request-ID`.

Run three processes from the backend image: `gunicorn` (default CMD),
`celery -A config worker -l info`, `celery -A config beat -l info`.

### Backups

`scripts/backup.sh` runs `pg_dump --format=custom` and copies it to
`s3://$BACKUP_BUCKET/pg/`. Schedule it nightly (cron or a Kubernetes CronJob).
`scripts/restore.sh <dump> <target DATABASE_URL>` restores into an empty
database and prints row counts. The procedure was rehearsed on the dev stack
on 2026-09-04 (520 invoices in, 520 out); the exact commands are in the script header.

## Runbooks

### Extraction backlog
Symptom: documents stuck in `pending`/`extracting`, `/api/health` shows celery ok.
1. `docker compose logs worker --tail 200 | grep extract_document` — look for
   `RateLimitError` (Anthropic 429) or `AuthenticationError`.
2. Check spend cap in the Anthropic console; `ANTHROPIC_API_KEY` in `.env`.
3. Scale workers: `docker compose up -d --scale worker=3`.
4. Re-queue stuck docs: `manage.py shell -c "from apps.documents.models import *; from apps.documents.tasks import extract_document; [extract_document.delay(str(d.pk)) for d in Document.objects.filter(status='pending')]"`.
5. Documents that failed 3 times are `failed` with `error` set; fix the cause, then POST `/api/documents/{id}/reextract`.

### A bad prompt version shipped
Every `ExtractionRun` / `EmailDraft` stores `prompt_version`. To roll back:
1. `git revert` the prompt file change under `backend/prompts/` and redeploy the worker.
2. Find affected runs: `ExtractionRun.objects.filter(prompt_version="extract_invoice_v2")`.
3. Invoices from those runs are still `needs_review` (auto-confirm is off by default);
   re-extract them with `/reextract` or bulk from a shell. Never edit an existing run.

### Mailbox token revoked
Symptom: `MailboxConnection.status = error`, sync task logs `invalid_grant` / 401.
1. `/settings/mailboxes` shows the mailbox as disconnected. An owner clicks
   Connect again (`POST /api/mail/connect/{provider}`), which stores fresh tokens.
2. Send scope is requested again on the next approval (progressive consent).
3. Sync resumes from `sync_cursor`; if the provider rejects the cursor the
   connector re-lists the last 30 days and de-duplicates on `provider_message_id`.

### Forecast bands miscalibrated
Symptom: `/forecast` badge shows coverage outside 75–90%.
1. `GET /api/forecast/backtest` — check `n_origins`; under 6 origins the metric is noise.
2. Coverage too LOW (bands too narrow): a party's history changed regime. Confirm
   recurring patterns and fixed lines in `/forecast`; consider the collection-policy
   scenario to see the shift.
3. Coverage too HIGH (bands too wide): usually one erratic customer dominating.
   Check `/api/forecast/risk/customers` and mark written-off invoices.
4. The deterministic path is always shown; bands are hidden automatically under
   90 days of history. Nothing here is a prediction of the economy (§8.1).

## Layout

See CLAUDE.md §8. Backend apps: accounts, parties, documents, invoices, gst,
payments, reconciliation, reporting, mail, forecasting. Pure logic lives in
`apps/*/domain/` with 100% branch coverage.
