#!/usr/bin/env bash
# Dev rehearsal: dump the compose Postgres to /tmp/nexren_local.dump
set -euo pipefail
docker compose exec -T postgres pg_dump -U nexren -d nexren --format=custom --no-owner > /tmp/nexren_local.dump
ls -la /tmp/nexren_local.dump
