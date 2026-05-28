#!/usr/bin/env bash
# One-shot setup: start 3 Dependency-Track instances, generate SBOMs, upload them.
#
# Usage:
#   SERVER_HOST=<public-ip> ./run.sh
#
# Optional env vars:
#   DT_ADMIN_PASSWORD   admin password to set on first login (default: ChangeMe123!)
#   SKIP_UP=1           don't (re)start containers
#   SKIP_SBOMS=1        don't (re)generate SBOMs (expects ./sboms/*.cdx.json to exist)
set -euo pipefail
cd "$(dirname "$0")"
HERE="$(pwd)"

# ---- resolve SERVER_HOST ----
: "${SERVER_HOST:=}"
if [ -z "${SERVER_HOST}" ]; then
  SERVER_HOST="$(hostname -I 2>/dev/null | awk '{print $1}')"
  echo "WARNING: SERVER_HOST not set; guessing this host's IP: ${SERVER_HOST}"
  echo "         If the browser can't reach the API from elsewhere, re-run with:"
  echo "             SERVER_HOST=<public-ip> ./run.sh"
fi
export SERVER_HOST
export DT_ADMIN_PASSWORD="${DT_ADMIN_PASSWORD:-ChangeMe123!}"
SKIP_UP="${SKIP_UP:-0}"
SKIP_SBOMS="${SKIP_SBOMS:-0}"

echo "=================================================="
echo "  dept-track-multi setup"
echo "  SERVER_HOST     = $SERVER_HOST"
echo "  ADMIN_PASSWORD  = $DT_ADMIN_PASSWORD"
echo "=================================================="

# ---- prereqs ----
command -v docker  >/dev/null 2>&1 || { echo "ERROR: docker not found";  exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 1; }
command -v git     >/dev/null 2>&1 || { echo "ERROR: git not found";     exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERROR: 'docker compose' v2 plugin not found"; exit 1; }

# ---- 1. start the DT instances (they boot while we build SBOMs) ----
if [ "$SKIP_UP" != "1" ]; then
  echo; echo "==> [1/3] Starting Dependency-Track instances..."
  docker compose pull
  docker compose up -d
  docker compose ps
else
  echo; echo "==> [1/3] Skipping container startup (SKIP_UP=1)"
fi

# ---- 2. generate SBOMs ----
if [ "$SKIP_SBOMS" != "1" ]; then
  echo; echo "==> [2/3] Generating SBOMs (this can take a while on first run)..."
  bash gen_sboms.sh
else
  echo; echo "==> [2/3] Skipping SBOM generation (SKIP_SBOMS=1)"
fi

# ---- 3. authenticate, create projects, upload ----
echo; echo "==> [3/3] Configuring instances and uploading SBOMs..."
python3 setup_and_upload.py

# ---- summary ----
echo
echo "=================================================="
echo "  Done. Open the dashboards (login: admin / $DT_ADMIN_PASSWORD)"
echo "    Acme Corp        http://$SERVER_HOST:8091"
echo "    Beta Industries  http://$SERVER_HOST:8092"
echo "    Gamma Solutions  http://$SERVER_HOST:8093"
echo
echo "  API keys: $HERE/api_keys.json"
echo "  (Vulnerability counts populate a minute or two after upload.)"
echo "=================================================="
