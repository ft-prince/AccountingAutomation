#!/usr/bin/env bash
# Restore a pg_dump custom-format file into a fresh database.
# Rehearsed 2026-09-04 against the dev compose stack (520 invoices in, 520 out):
#   ./scripts/backup_local.sh
#   docker compose exec -T postgres psql -U nexren -d postgres \
#       -c "DROP DATABASE IF EXISTS nexren_restore" -c "CREATE DATABASE nexren_restore"
#   docker compose cp /tmp/nexren_local.dump postgres:/tmp/nexren_local.dump
#   docker compose exec -T postgres pg_restore --no-owner --no-privileges -U nexren -d nexren_restore /tmp/nexren_local.dump
#   docker compose exec -T postgres psql -U nexren -d nexren_restore -tAc "SELECT count(*) FROM invoices_invoice;"
# Production: point TARGET at a NEW database, verify counts, then switch DATABASE_URL and restart.
set -euo pipefail
FILE=${1:?dump file}; TARGET=${2:?target DATABASE_URL of an EMPTY database}
pg_restore --no-owner --no-privileges --dbname="$TARGET" "$FILE"
psql "$TARGET" -tAc "SELECT 'invoices', count(*) FROM invoices_invoice UNION ALL SELECT 'payments', count(*) FROM payments_payment;"
echo "restore ok into $TARGET"
