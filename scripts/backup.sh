#!/usr/bin/env bash
# MANUAL FALLBACK. The primary path is the Celery Beat task
# apps.accounts.tasks.run_database_backup ("database-backup-nightly" in config/celery.py),
# which records a BackupRun row and raises an in-app notification when a backup fails or
# goes stale. Use this script for an ad-hoc dump, or when Beat is not running.
# Requires: DATABASE_URL, BACKUP_BUCKET, S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY (from .env).
set -euo pipefail
: "${DATABASE_URL:?}" "${BACKUP_BUCKET:?}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FILE="/tmp/nexren_${STAMP}.dump"
pg_dump --format=custom --no-owner --dbname="$DATABASE_URL" --file="$FILE"
AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY" \
  aws --endpoint-url "${S3_ENDPOINT_URL:-https://s3.ap-south-1.amazonaws.com}" \
  s3 cp "$FILE" "s3://${BACKUP_BUCKET}/pg/nexren_${STAMP}.dump" --only-show-errors
rm -f "$FILE"
echo "backup ok: pg/nexren_${STAMP}.dump"
