#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# backup.sh — Daily PostgreSQL backup
#
# Runs inside the db_backup container on a cron schedule (02:00 daily).
# Writes compressed dumps to /backups and prunes files older than
# BACKUP_RETAIN_DAYS (default 7).
#
# Backup filename format:
#   backup_<DBNAME>_<YYYY-MM-DD_HHMMSS>.sql.gz
#
# To restore a backup manually see scripts/restore.sh
# ══════════════════════════════════════════════════════════════════════════════
set -e

TIMESTAMP=$(date +"%Y-%m-%d_%H%M%S")
BACKUP_DIR="/backups"
FILENAME="backup_${POSTGRES_DB}_${TIMESTAMP}.sql.gz"
RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-7}"

echo "[backup] Starting backup of ${POSTGRES_DB} at ${TIMESTAMP}"

# Run pg_dump and compress immediately — never writes an uncompressed file
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h "${PGHOST:-db}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    -Fp \
    --no-password \
    | gzip -9 > "${BACKUP_DIR}/${FILENAME}"

SIZE=$(du -sh "${BACKUP_DIR}/${FILENAME}" | cut -f1)
echo "[backup] ✅ Written: ${FILENAME} (${SIZE})"

# Prune backups older than RETAIN_DAYS
echo "[backup] Pruning backups older than ${RETAIN_DAYS} days..."
find "${BACKUP_DIR}" -name "backup_*.sql.gz" -mtime "+${RETAIN_DAYS}" -print -delete

REMAINING=$(find "${BACKUP_DIR}" -name "backup_*.sql.gz" | wc -l)
echo "[backup] Done. ${REMAINING} backup(s) retained."