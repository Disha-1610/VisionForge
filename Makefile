# ============================================================
# VisionForge-AI — Makefile
# ============================================================
# Usage:
#   make help          Show all available commands
#   make setup         First-time project setup
#   make dev           Start backend dev server
#   make test          Run all tests
# ============================================================

.PHONY: help setup venv install dev run test lint format migrate \
        docker-build docker-up docker-down clean

# ── Variables ────────────────────────────────────────────────
PYTHON      = python
PIP         = pip
UVICORN     = uvicorn
ALEMBIC     = alembic
PYTEST      = pytest
BACKEND_DIR = backend
APP_MODULE  = app.main:app

# ── Help ─────────────────────────────────────────────────────
help: ## Show this help message
	@echo.
	@echo   VisionForge-AI - Available Commands
	@echo   ==================================
	@echo.
	@echo   setup          First-time project setup (venv + install + env)
	@echo   venv           Create Python virtual environment
	@echo   install        Install all dependencies
	@echo   dev            Start backend dev server with auto-reload
	@echo   run            Start backend production server
	@echo   test           Run all tests
	@echo   lint           Run linter (ruff)
	@echo   format         Auto-format code (ruff)
	@echo   migrate        Run database migrations
	@echo   migrate-new    Create a new migration (usage: make migrate-new msg="description")
	@echo   docker-build   Build Docker containers
	@echo   docker-up      Start all services via Docker Compose
	@echo   docker-down    Stop all Docker services
	@echo   clean          Remove __pycache__, .pyc, temp files
	@echo.

# ── Setup ────────────────────────────────────────────────────
venv: ## Create virtual environment
	$(PYTHON) -m venv venv
	@echo Virtual environment created. Activate it with: venv\Scripts\activate

install: ## Install dependencies
	cd $(BACKEND_DIR) && $(PIP) install -r requirements.txt

setup: venv install ## Full first-time setup
	@if not exist .env copy .env.example .env
	@echo.
	@echo   Setup complete! Next steps:
	@echo   1. Activate venv:  venv\Scripts\activate
	@echo   2. Edit .env with your database credentials
	@echo   3. Run:  make migrate
	@echo   4. Run:  make dev
	@echo.

# ── Development ──────────────────────────────────────────────
dev: ## Start dev server with auto-reload
	cd $(BACKEND_DIR) && $(UVICORN) $(APP_MODULE) --host 0.0.0.0 --port 8000 --reload

run: ## Start production server
	cd $(BACKEND_DIR) && $(UVICORN) $(APP_MODULE) --host 0.0.0.0 --port 8000 --workers 4

# ── Testing ──────────────────────────────────────────────────
test: ## Run all tests
	cd $(BACKEND_DIR) && $(PYTEST) tests/ -v

test-cov: ## Run tests with coverage
	cd $(BACKEND_DIR) && $(PYTEST) tests/ -v --cov=app --cov-report=html

# ── Linting & Formatting ────────────────────────────────────
lint: ## Run linter
	cd $(BACKEND_DIR) && ruff check app/

format: ## Auto-format code
	cd $(BACKEND_DIR) && ruff format app/

# ── Database ─────────────────────────────────────────────────
migrate: ## Run all pending migrations
	cd $(BACKEND_DIR) && $(ALEMBIC) upgrade head

migrate-new: ## Create new migration (usage: make migrate-new msg="add users table")
	cd $(BACKEND_DIR) && $(ALEMBIC) revision --autogenerate -m "$(msg)"

migrate-down: ## Rollback last migration
	cd $(BACKEND_DIR) && $(ALEMBIC) downgrade -1

# ── Docker ───────────────────────────────────────────────────
docker-build: ## Build Docker images
	docker-compose build

docker-up: ## Start all services
	docker-compose up -d

docker-down: ## Stop all services
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

# ── Cleanup ──────────────────────────────────────────────────
clean: ## Remove cache and temp files
	@echo Cleaning up...
	@for /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
	@del /s /q *.pyc 2>nul
	@if exist .pytest_cache rd /s /q .pytest_cache
	@if exist htmlcov rd /s /q htmlcov
	@if exist .ruff_cache rd /s /q .ruff_cache
	@echo Done.
