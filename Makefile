# ══════════════════════════════════════════════════════════════════════════════
# Simurgh AI — Makefile
#
# Quick reference:
#   make install   — first-time dev setup (copies .env, builds, migrates, seeds)
#   make dev       — start the full dev stack with hot-reload
#   make stop      — stop all containers
#   make test      — run all backend test tiers
#   make lint      — lint + format check (backend & frontend)
#   make prod      — build & start the production stack
#   make migrate   — apply pending Alembic migrations
#   make logs      — tail backend + worker logs
#   make help      — list every target with descriptions
# ══════════════════════════════════════════════════════════════════════════════

# ── Internal config ───────────────────────────────────────────────────────────
COMPOSE      := docker compose
COMPOSE_PROD := docker compose -f docker-compose.prod.yml
BACKEND      := $(COMPOSE) exec -T backend
BOLD         := \033[1m
GREEN        := \033[0;32m
YELLOW       := \033[1;33m
CYAN         := \033[0;36m
RESET        := \033[0m

.DEFAULT_GOAL := help
# Prevent make from treating target names as files
.PHONY: help install dev stop restart build migrate seed logs shell \
        test test-unit test-api test-integration test-e2e \
        lint lint-backend lint-frontend fmt \
        prod prod-init prod-stop prod-logs prod-migrate \
        backup restore superuser clean nuke


# ══════════════════════════════════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════════════════════════════════

help: ## Show this help message
	@echo ""
	@echo "$(BOLD)Simurgh AI$(RESET)"
	@echo ""
	@echo "$(CYAN)Dev workflow$(RESET)"
	@grep -E '^(install|dev|stop|restart|build|migrate|seed|logs|shell):.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Tests$(RESET)"
	@grep -E '^test[^:]*:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Code quality$(RESET)"
	@grep -E '^(lint|fmt)[^:]*:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Production$(RESET)"
	@grep -E '^prod[^:]*:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Utilities$(RESET)"
	@grep -E '^(backup|restore|superuser|clean|nuke):.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""


# ══════════════════════════════════════════════════════════════════════════════
# DEV WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════

install: ## First-time setup: copy .env, build images, migrate DB, seed demo data
	@echo "$(GREEN)► Checking prerequisites...$(RESET)"
	@command -v docker  >/dev/null 2>&1 || (echo "$(YELLOW)Docker not found. Install from https://docs.docker.com/get-docker/$(RESET)" && exit 1)
	@docker compose version >/dev/null 2>&1 || (echo "$(YELLOW)Docker Compose plugin not found. Update Docker Desktop or install the plugin.$(RESET)" && exit 1)
	@echo "$(GREEN)► Setting up .env...$(RESET)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(YELLOW)  .env created from .env.example — fill in ANTHROPIC_API_KEY, SECRET_KEY, and ENCRYPTION_KEY before continuing.$(RESET)"; \
		echo "$(YELLOW)  Generate keys:$(RESET)"; \
		echo "$(YELLOW)    SECRET_KEY:      openssl rand -hex 32$(RESET)"; \
		echo "$(YELLOW)    ENCRYPTION_KEY:  python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"$(RESET)"; \
		echo ""; \
		read -p "Press Enter once .env is filled in, or Ctrl+C to abort..."; \
	else \
		echo "  .env already exists — skipping copy."; \
	fi
	@$(MAKE) build
	@$(MAKE) migrate
	@$(MAKE) seed
	@echo ""
	@echo "$(GREEN)✓ Setup complete!$(RESET)"
	@echo ""
	@echo "  Frontend:   http://localhost:5173"
	@echo "  Backend:    http://localhost:8000"
	@echo "  API docs:   http://localhost:8000/api/v1/docs"
	@echo ""
	@echo "  Run $(BOLD)make dev$(RESET) to start the stack."
	@echo "  Run $(BOLD)make superuser$(RESET) to create your admin account."

dev: ## Start the full dev stack (hot-reload backend + Vite frontend)
	@echo "$(GREEN)► Starting dev stack...$(RESET)"
	$(COMPOSE) up

stop: ## Stop all running containers
	@echo "$(GREEN)► Stopping containers...$(RESET)"
	$(COMPOSE) down

restart: ## Restart the dev stack (stop + start)
	@$(MAKE) stop
	@$(MAKE) dev

build: ## Build (or rebuild) all Docker images
	@echo "$(GREEN)► Building images...$(RESET)"
	$(COMPOSE) up --build --wait --no-start
	@echo "$(GREEN)✓ Images built.$(RESET)"

migrate: ## Apply all pending Alembic migrations
	@echo "$(GREEN)► Running database migrations...$(RESET)"
	$(COMPOSE) up -d db redis
	@echo "  Waiting for database to be ready..."
	@$(COMPOSE) run --rm -T backend sh -c \
		"until pg_isready -h db -U postgres 2>/dev/null; do sleep 1; done"
	$(COMPOSE) run --rm -T backend alembic upgrade head
	@echo "$(GREEN)✓ Migrations applied.$(RESET)"

requeue: ## Re-dispatch vectorization for all PENDING/FAILED documents (fixes stuck seed data)
	docker compose exec backend python scripts/requeue_pending_documents.py

requeue-dry: ## Show which documents would be requeued without doing it
	docker compose exec backend python scripts/requeue_pending_documents.py --dry-run

seed: ## Seed demo data and experiment scenarios into the database
	@echo "$(GREEN)► Seeding database...$(RESET)"
	$(COMPOSE) up -d db redis
	$(COMPOSE) run --rm -T -e PYTHONPATH=/app backend python -m app.db.seed_data
	$(COMPOSE) run --rm -T -e PYTHONPATH=/app backend python -m app.db.seed_scenarios
	@echo "$(GREEN)✓ Database seeded.$(RESET)"

logs: ## Tail live logs for backend and celery worker
	$(COMPOSE) logs -f backend celery_worker

shell: ## Open a bash shell inside the running backend container
	$(COMPOSE) exec backend bash


# ══════════════════════════════════════════════════════════════════════════════
# TESTS
# ══════════════════════════════════════════════════════════════════════════════

test: ## Run all backend test tiers (unit + api + integration)
	@$(MAKE) test-unit
	@$(MAKE) test-api
	@$(MAKE) test-integration

test-unit: ## Run unit tests only (no database or network required)
	@echo "$(GREEN)► Running unit tests...$(RESET)"
	$(COMPOSE) run --rm -T backend \
		pytest tests/unit/ -v --tb=short -m "not slow"

test-api: ## Run API / HTTP layer tests (mocked DB, no real PostgreSQL)
	@echo "$(GREEN)► Running API tests...$(RESET)"
	$(COMPOSE) up -d db redis
	$(COMPOSE) run --rm -e PYTHONPATH=/app backend pytest tests/api/ -v --tb=short

test-integration: ## Run integration tests against real PostgreSQL + Redis
	@echo "$(GREEN)► Running integration tests...$(RESET)"
	$(COMPOSE) up -d db redis
	$(COMPOSE) run --rm -e PYTHONPATH=/app backend pytest tests/integration/ -v --tb=short -m "not slow"

test-e2e: ## Run end-to-end flow tests (requires full stack running)
	@echo "$(GREEN)► Running e2e tests...$(RESET)"
	$(COMPOSE) up -d
	@sleep 5
	$(BACKEND) pytest tests/e2e/ -v --tb=short


# ══════════════════════════════════════════════════════════════════════════════
# CODE QUALITY
# ══════════════════════════════════════════════════════════════════════════════

lint: lint-backend lint-frontend ## Run all linters (backend Ruff + frontend ESLint/tsc)

lint-backend: ## Lint and format-check the backend with Ruff
	@echo "$(GREEN)► Backend lint (Ruff)...$(RESET)"
	cd backend && ruff check .
	cd backend && ruff format . --check

lint-frontend: ## Lint and type-check the frontend (ESLint + tsc)
	@echo "$(GREEN)► Frontend lint (ESLint + tsc)...$(RESET)"
	cd frontend && npm run lint
	cd frontend && npx tsc --noEmit

fmt: ## Auto-fix backend formatting and lint errors with Ruff
	@echo "$(GREEN)► Auto-formatting backend...$(RESET)"
	cd backend && ruff check . --fix
	cd backend && ruff format .
	@echo "$(GREEN)✓ Backend formatted.$(RESET)"


# ══════════════════════════════════════════════════════════════════════════════
# PRODUCTION
# ══════════════════════════════════════════════════════════════════════════════

prod: ## Build and start the production stack (requires HTTPS domain in .env)
	@echo "$(GREEN)► Starting production stack...$(RESET)"
	@test -f .env || (echo "$(YELLOW).env not found — copy .env.example and fill in production values.$(RESET)" && exit 1)
	$(COMPOSE_PROD) up --build -d
	@sleep 5
	@$(MAKE) prod-migrate
	@echo ""
	@echo "$(GREEN)✓ Production stack running.$(RESET)"
	@$(COMPOSE_PROD) ps

prod-init: ## First-time production deploy: provisions SSL cert and seeds DB
	@echo "$(GREEN)► Running first-time production init...$(RESET)"
	bash deploy.sh --init

prod-stop: ## Stop the production stack
	$(COMPOSE_PROD) down

prod-migrate: ## Apply Alembic migrations in production
	@echo "$(GREEN)► Applying production migrations...$(RESET)"
	$(COMPOSE_PROD) exec -T backend alembic upgrade head

prod-logs: ## Tail production backend + worker logs
	$(COMPOSE_PROD) logs -f backend celery_worker


# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

superuser: ## Create an admin account (prompts for email and password)
	@echo "$(GREEN)► Creating superuser...$(RESET)"
	$(COMPOSE) up -d db redis
	$(COMPOSE) run --rm -e PYTHONPATH=/app backend python scripts/create_superuser.py


backup: ## Run a manual database backup (dev stack)
	@echo "$(GREEN)► Creating database backup...$(RESET)"
	$(COMPOSE) exec db sh -c \
		'pg_dump -U postgres hero_db | gzip > /tmp/backup_$$(date +%Y%m%d_%H%M%S).sql.gz && echo "Backup saved to container /tmp/"'

restore: ## Restore database from a backup file (usage: make restore FILE=backup.sql.gz)
ifndef FILE
	@echo "$(YELLOW)Usage: make restore FILE=path/to/backup.sql.gz$(RESET)"
	@exit 1
endif
	@echo "$(GREEN)► Restoring from $(FILE)...$(RESET)"
	$(COMPOSE) exec -T db sh -c "gunzip -c - | psql -U postgres hero_db" < $(FILE)
	@echo "$(GREEN)✓ Restore complete.$(RESET)"

clean: ## Remove stopped containers and dangling images (keeps volumes)
	@echo "$(GREEN)► Cleaning up containers and images...$(RESET)"
	$(COMPOSE) down --remove-orphans
	docker image prune -f
	@echo "$(GREEN)✓ Clean complete.$(RESET)"

nuke: ## ⚠ DANGER: remove all containers, images, AND volumes (destroys all data)
	@echo "$(YELLOW)⚠ This will destroy all containers, images, and database volumes.$(RESET)"
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	$(COMPOSE) down -v --remove-orphans
	docker image prune -af
	@echo "$(GREEN)✓ Everything removed.$(RESET)"