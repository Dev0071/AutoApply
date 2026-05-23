VENV = .venv/bin
DB_URL = postgresql://buglens:buglens_dev_password@localhost:5432/autoapply

# ── Infrastructure ────────────────────────────────────────────────────────────

infra:                        ## Start Postgres + Redis containers
	docker start buglens-postgres buglens-redis

infra-stop:                   ## Stop containers
	docker stop buglens-postgres buglens-redis

# ── Database ──────────────────────────────────────────────────────────────────

migrate:                      ## Apply all pending migrations
	DATABASE_URL=$(DB_URL) $(VENV)/alembic upgrade head

migrate-down:                 ## Roll back one migration
	DATABASE_URL=$(DB_URL) $(VENV)/alembic downgrade -1

db-reset:                     ## Drop + recreate autoapply database and migrate
	docker exec buglens-postgres psql -U buglens -d buglens_dev \
	  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='autoapply';" > /dev/null 2>&1; true
	docker exec buglens-postgres psql -U buglens -d buglens_dev \
	  -c "DROP DATABASE IF EXISTS autoapply; CREATE DATABASE autoapply;"
	DATABASE_URL=$(DB_URL) $(VENV)/alembic upgrade head

db:                           ## Open a psql shell in autoapply db
	docker exec -it buglens-postgres psql -U buglens -d autoapply

# ── Backend ───────────────────────────────────────────────────────────────────

api:                          ## Run FastAPI dev server on :8000
	$(VENV)/uvicorn backend.api.main:app --reload

worker:                       ## Run Celery worker
	$(VENV)/celery -A backend.workers.tasks.celery_app worker --loglevel=info -Q applications

# ── Frontend ──────────────────────────────────────────────────────────────────

ui:                           ## Run Next.js dev server on :3000
	cd frontend && npm run dev

ui-install:                   ## Install frontend dependencies
	cd frontend && npm install

# ── Tests ─────────────────────────────────────────────────────────────────────

test:                         ## Run all unit tests
	$(VENV)/python -m pytest --ignore=tests/agents/test_vision_loop_integration.py -v

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

.PHONY: infra infra-stop migrate migrate-down db-reset db api worker ui ui-install test help
