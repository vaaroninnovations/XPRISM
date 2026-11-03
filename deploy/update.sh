#!/usr/bin/env bash
# Deploy a new version: run as root from the unpacked new package folder.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
rsync -a --exclude '.env' --exclude 'db.sqlite3' "$SRC"/ /opt/xprism/app/ 2>/dev/null || cp -r "$SRC"/. /opt/xprism/app/
chown -R xprism:www-data /opt/xprism
cd /opt/xprism/app
/opt/xprism/venv/bin/pip install -r requirements.txt
sudo -u xprism /opt/xprism/venv/bin/python manage.py migrate --noinput
sudo -u xprism /opt/xprism/venv/bin/python manage.py collectstatic --noinput
sudo -u xprism /opt/xprism/venv/bin/python manage.py bootstrap_lab
systemctl restart xprism
echo "Updated."
