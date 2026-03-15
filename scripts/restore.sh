#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# restore.sh — Restore a PostgreSQL backup
#
# Usage:
#   bash scripts/restore.sh <backup_file>
#
# Example:
#   bash scripts/restore.sh backup_mydb_2025-01-15_020001.sql.gz
#
# The backup file must exist inside the db_backups Docker volume.
# This script runs pg_restore inside the db container.
#
# ⚠️  WARNING: This DROPS and recreates the target database.
#    All current data will be permanently lost.
#    Always verify the backup file before running.
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; NC="\033[0m"
info() { echo -e "${GREEN}[restore]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $*"; }
die()  { echo -e "${RED}[error]${NC} $*"; exit 1; }

COMPOSE="docker compose -f docker-compose.prod.yml"

# ── Args ──────────────────────────────────────────────────────────────────────
[[ $# -eq 1 ]] || die "Usage: bash scripts/restore.sh <backup_filename>"
BACKUP_FILE="$1"

# ── Preflight ─────────────────────────────────────────────────────────────────
[[ -f .env ]] || die ".env not found"
source .env

info "Checking backup file exists in volume..."
$COMPOSE run --rm db_backup test -f "/backups/${BACKUP_FILE}" \
    || die "Backup file not found: /backups/${BACKUP_FILE}"

# List available backups for reference
info "Available backups:"
$COMPOSE run --rm db_backup sh -c "ls -lh /backups/backup_*.sql.gz 2>/dev/null || echo '  (none)'"

# ── Confirmation ──────────────────────────────────────────────────────────────
echo ""
warn "⚠️  You are about to restore: ${BACKUP_FILE}"
warn "⚠️  This will DROP the current database '${POSTGRES_DB}' and restore from the backup."
warn "⚠️  ALL CURRENT DATA WILL BE LOST."
echo ""
read -r -p "Type YES to confirm: " CONFIRM
[[ "$CONFIRM" == "YES" ]] || die "Aborted."

# ── Stop backend and celery to prevent writes during restore ──────────────────
info "Stopping backend and celery workers..."
$COMPOSE stop backend celery_worker

# ── Restore ───────────────────────────────────────────────────────────────────
info "Restoring ${BACKUP_FILE}..."
$COMPOSE run --rm db_backup sh -c "
    PGPASSWORD='${POSTGRES_PASSWORD}' psql \
        -h db \
        -U '${POSTGRES_USER}' \
        -c 'DROP DATABASE IF EXISTS ${POSTGRES_DB};'
    PGPASSWORD='${POSTGRES_PASSWORD}' psql \
        -h db \
        -U '${POSTGRES_USER}' \
        -c 'CREATE DATABASE ${POSTGRES_DB};'
    gunzip -c '/backups/${BACKUP_FILE}' | PGPASSWORD='${POSTGRES_PASSWORD}' psql \
        -h db \
        -U '${POSTGRES_USER}' \
        -d '${POSTGRES_DB}'
"

info "✅ Restore complete."

# ── Restart services ──────────────────────────────────────────────────────────
info "Restarting backend and celery workers..."
$COMPOSE start backend celery_worker

info "Running migrations to ensure schema is up to date..."
sleep 3
$COMPOSE exec -T backend alembic upgrade head

info "🎉 Database restored successfully from ${BACKUP_FILE}"
info "Run '$COMPOSE ps' to verify all services are healthy."