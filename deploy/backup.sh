#!/usr/bin/env bash
# Daily database backup, keeps 14 days.  Install:  sudo cp deploy/backup.sh /etc/cron.daily/xprism-backup && sudo chmod +x /etc/cron.daily/xprism-backup
set -euo pipefail
DEST=/var/backups/xprism; mkdir -p "$DEST"; chmod 700 "$DEST"
STAMP=$(date +%F)
# read only the values we need from .env (never execute it)
getenv() { grep -E "^$1=" /opt/xprism/app/.env | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }
POSTGRES_DB=$(getenv POSTGRES_DB); POSTGRES_USER=$(getenv POSTGRES_USER); POSTGRES_PASSWORD=$(getenv POSTGRES_PASSWORD); POSTGRES_HOST=$(getenv POSTGRES_HOST)
if [ -n "${POSTGRES_DB:-}" ]; then
  PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h "${POSTGRES_HOST:-127.0.0.1}" -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "$DEST/db-$STAMP.dump"
else
  sqlite3 /opt/xprism/app/db.sqlite3 ".backup '$DEST/db-$STAMP.sqlite3'"
fi
find "$DEST" -type f -mtime +14 -delete
