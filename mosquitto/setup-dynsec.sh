#!/usr/bin/env bash
# One-time dynsec bootstrap. Run as root inside the Mosquitto container, after
# installing dynsec.conf but BEFORE restarting the broker (init refuses to run
# over an existing file, and the plugin creates an empty one on first start).
#
#   ./setup-dynsec.sh <your-admin-username>
#
# Prompts for passwords so they never land in shell history or process lists.
set -euo pipefail

ME="${1:?usage: $0 <your-admin-username>}"
CFG=/var/lib/mosquitto/dynamic-security.json
SVC=portal-svc
ADMIN_ROLE=portal-admin
BROKER=(-h 127.0.0.1 -p 1883)

command -v mosquitto_ctrl >/dev/null || { echo "Install mosquitto-clients for mosquitto_ctrl." >&2; exit 1; }
[ -e "$CFG" ] && { echo "$CFG exists. Remove it only if you mean to start over." >&2; exit 1; }

read -r -s -p "Password for the dynsec bootstrap admin '$SVC' (the app's service account): " SVC_PW; echo
read -r -s -p "Password for your personal admin login '$ME': " ME_PW; echo

# init creates the client $SVC holding the built-in 'admin' role ($CONTROL access only).
mosquitto_ctrl dynsec init "$CFG" "$SVC" "$SVC_PW"
chown mosquitto:mosquitto "$CFG"
chmod 600 "$CFG"

systemctl restart mosquitto
sleep 1

ctrl() { mosquitto_ctrl "${BROKER[@]}" -u "$SVC" -P "$SVC_PW" dynsec "$@"; }

# A marker role: it grants no topics, it only says "may use the web admin page".
ctrl createRole "$ADMIN_ROLE"
ctrl createClient "$ME" -p "$ME_PW"
ctrl addClientRole "$ME" "$ADMIN_ROLE"

cat <<EOF

Done. The app's service account is '$SVC'; put its password in /etc/mqtt-admin.env
as MQTT_SVC_PASSWORD. You can sign in to the admin page as '$ME'.

Next, create the topic roles your publishers and dashboards need, for example:
  mosquitto_ctrl -u $SVC -P ... dynsec createRole sensor-publisher
  mosquitto_ctrl -u $SVC -P ... dynsec addRoleACL sensor-publisher publishClientSend 'sensors/#' allow 10
Roles you create appear as checkboxes in the web UI.
EOF
