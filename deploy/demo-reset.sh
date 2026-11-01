#!/usr/bin/env bash
# Nightly reset of the public demo logins and their sample class.  Install:  sudo cp deploy/demo-reset.sh /etc/cron.daily/xprism-demo-reset && sudo chmod +x /etc/cron.daily/xprism-demo-reset
set -euo pipefail
cd /opt/xprism/app
sudo -u xprism /opt/xprism/venv/bin/python manage.py setup_demo
