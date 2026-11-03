#!/usr/bin/env bash
# One-time server setup for Ubuntu 22.04 / 24.04.  Run as root from the unpacked package folder:
#   sudo bash deploy/setup.sh lab.example.com admin@example.com
set -euo pipefail
DOMAIN="${1:?usage: setup.sh <domain> <admin-email>}"
ADMIN_EMAIL="${2:?usage: setup.sh <domain> <admin-email>}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"

apt-get update
apt-get install -y python3 python3-venv python3-pip nginx postgresql sqlite3 certbot python3-certbot-nginx

id xprism >/dev/null 2>&1 || useradd --system --home /opt/xprism --shell /usr/sbin/nologin xprism
mkdir -p /opt/xprism/app /opt/xprism/static
cp -r "$SRC"/. /opt/xprism/app/
python3 -m venv /opt/xprism/venv
/opt/xprism/venv/bin/pip install --upgrade pip
/opt/xprism/venv/bin/pip install -r /opt/xprism/app/requirements.txt

# database
DBPASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='xprism'" | grep -q 1 || sudo -u postgres psql -c "CREATE USER xprism WITH PASSWORD '$DBPASS';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='xprism'" | grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE xprism OWNER xprism;"

# environment file
if [ ! -f /opt/xprism/app/.env ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
  sed -e "s#change-me-to-a-long-random-string#$SECRET#" -e "s#lab.example.com#$DOMAIN#g" -e "s#POSTGRES_PASSWORD=change-me#POSTGRES_PASSWORD=$DBPASS#" \
      /opt/xprism/app/deploy/env.example > /opt/xprism/app/.env
fi
chown -R xprism:www-data /opt/xprism
chmod 600 /opt/xprism/app/.env

cd /opt/xprism/app
sudo -u xprism /opt/xprism/venv/bin/python manage.py migrate --noinput
sudo -u xprism /opt/xprism/venv/bin/python manage.py createcachetable
sudo -u xprism /opt/xprism/venv/bin/python manage.py collectstatic --noinput
sudo -u xprism /opt/xprism/venv/bin/python manage.py bootstrap_lab

# services
cp deploy/xprism.service /etc/systemd/system/
cp deploy/nginx-ratelimit.conf /etc/nginx/conf.d/xprism-ratelimit.conf
sed "s/lab.example.com/$DOMAIN/" deploy/nginx-xprism.conf > /etc/nginx/sites-available/xprism
ln -sf /etc/nginx/sites-available/xprism /etc/nginx/sites-enabled/xprism
rm -f /etc/nginx/sites-enabled/default
cp deploy/backup.sh /etc/cron.daily/xprism-backup && chmod +x /etc/cron.daily/xprism-backup
systemctl daemon-reload
systemctl enable --now xprism
nginx -t && systemctl reload nginx

echo
echo "Now create your super admin account:"
echo "  cd /opt/xprism/app && sudo -u xprism /opt/xprism/venv/bin/python manage.py bootstrap_lab --admin-username superadmin --admin-email $ADMIN_EMAIL --admin-password 'CHOOSE-A-STRONG-PASSWORD'"
echo "Then enable HTTPS:"
echo "  certbot --nginx -d $DOMAIN --redirect -m $ADMIN_EMAIL --agree-tos"
