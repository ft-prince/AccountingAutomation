.PHONY: up down test lint migrate shell gen-types

BE = docker compose exec backend
PY = cd backend && .venv/bin

up:
	docker compose up -d --build

down:
	docker compose down

test:
	cd backend && .venv/bin/pytest -q
	cd frontend && npm test

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy apps
	cd frontend && npm run lint

migrate:
	$(BE) python manage.py migrate

shell:
	$(BE) python manage.py shell

gen-types:
	cd frontend && npm run gen:types
