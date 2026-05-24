#!/usr/bin/env bash
# start-local.sh — Run this on your local machine
# Starts LiveKit server, agent, frontend, and ngrok (for SIP)
set -euo pipefail

ENV_FILE=".env.local"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found."
  echo "Copy .env.local.example to .env.local and fill in your values."
  exit 1
fi

# ── Load env ────────────────────────────────────────────────────────────────
set -o allexport
source "$ENV_FILE"
set +o allexport

# ── Check Tailscale IP ───────────────────────────────────────────────────────
REMOTE_HOST=$(grep -oP 'STT_BASE_URL=http://\K[^:]+' "$ENV_FILE" 2>/dev/null || echo "")

if [ -z "$REMOTE_HOST" ] || [ "$REMOTE_HOST" = "<TAILSCALE_IP>" ]; then
  echo "ERROR: Please update $ENV_FILE with your vast.ai Tailscale IP."
  echo "Replace <TAILSCALE_IP> with the actual IP (e.g., 100.64.0.5)"
  exit 1
fi

echo "========================================"
echo "  Starting local stack"
echo "========================================"
echo ""
echo "Remote models host : $REMOTE_HOST"

# ── Check ngrok config ───────────────────────────────────────────────────────
NGROK_DOMAIN="${NGROK_DOMAIN:-}"
NGROK_AUTHTOKEN="${NGROK_AUTHTOKEN:-}"

if [ -z "$NGROK_AUTHTOKEN" ] || [ -z "$NGROK_DOMAIN" ]; then
  echo ""
  echo "⚠️  NGROK_AUTHTOKEN أو NGROK_DOMAIN غير محددين في $ENV_FILE"
  echo "   SIP لن يعمل بدون ngrok."
  echo "   للاستمرار بدون SIP اضغط Enter، أو Ctrl+C للإلغاء."
  read -r -p "" _
  SIP_ENABLED=false
else
  echo "ngrok domain      : $NGROK_DOMAIN"
  SIP_ENABLED=true
fi

# ── Check remote model connectivity ─────────────────────────────────────────
echo ""
echo "Checking remote model connectivity..."
FAILED=0
for endpoint in "$REMOTE_HOST:11435/v1/models" "$REMOTE_HOST:11436/v1/models"; do
  PORT=$(echo "$endpoint" | grep -oP ':\K[0-9]+')
  if curl -sf --connect-timeout 5 "http://$endpoint" > /dev/null 2>&1; then
    echo "  ✓ Port $PORT reachable"
  else
    echo "  ✗ Port $PORT NOT reachable"
    FAILED=1
  fi
done

if [ "$FAILED" -eq 1 ]; then
  echo ""
  echo "WARNING: Some remote model endpoints are not reachable."
  echo "Make sure the models are running on the vast.ai machine (./start-remote.sh)"
  echo ""
  read -r -p "Continue anyway? (y/N): " choice
  case "$choice" in
    y|Y) echo "Continuing..." ;;
    *) exit 1 ;;
  esac
fi

# ── Print info ───────────────────────────────────────────────────────────────
echo ""
echo "Services:"
echo "  • Frontend        → http://localhost:3000"
echo "  • LiveKit         → ws://localhost:7880"
echo "  • Agent           → connecting to remote models"
if [ "$SIP_ENABLED" = true ]; then
  echo "  • ngrok tunnel    → https://$NGROK_DOMAIN"
  echo "  • ngrok dashboard → http://localhost:4040"
  echo ""
  echo "📞 Twilio Origination URI:"
  echo "   sip:$NGROK_DOMAIN;transport=tcp"
fi
echo ""

# ── Start services ───────────────────────────────────────────────────────────
if [ "$SIP_ENABLED" = true ]; then
  docker compose \
    -f docker-compose.local.yml \
    --env-file .env.local \
    up --build "$@"
else
  # شغّل بدون ngrok service
  docker compose \
    -f docker-compose.local.yml \
    --env-file .env.local \
    up --build \
    --scale ngrok=0 "$@"
fi
