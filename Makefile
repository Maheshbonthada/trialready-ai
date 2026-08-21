.PHONY: install dev test lint typecheck migrate docker-up docker-down bicep-lint

install:
	pip install -e "apps/api[dev]"

dev:
	cd apps/api && uvicorn trialready_api.main:app --reload --app-dir src

test:
	cd apps/api && pytest

lint:
	ruff check apps/api/src apps/api/tests

typecheck:
	mypy apps/api/src

migrate:
	cd apps/api && alembic upgrade head

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

bicep-lint:
	az bicep build --file infra/bicep/main.bicep --stdout > /dev/null
