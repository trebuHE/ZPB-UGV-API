#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIM_DIR="$ROOT/src/panther-autonomy-pkg"
API_FILE="$ROOT/src/ugv-api/compose.api-sim.yaml"
CLIENT_DIR="$ROOT/src/client"
API_URL="${API_URL:-http://localhost:8000}"
KEEP="${KEEP:-0}"
SIM_PID=""
SIM_STARTED_WITH_SETSID=0

log() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

cleanup() {
  status=$?
  trap - EXIT INT TERM

  if [[ "$KEEP" == "1" ]]; then
    log "KEEP=1, leaving the API and simulation running."
    exit "$status"
  fi

  log "Stopping API and simulation..."
  docker compose -f "$API_FILE" down --remove-orphans >/dev/null 2>&1 || true

  if [[ -n "$SIM_PID" ]] && kill -0 "$SIM_PID" >/dev/null 2>&1; then
    if [[ "$SIM_STARTED_WITH_SETSID" == "1" ]]; then
      kill -- -"$SIM_PID" >/dev/null 2>&1 || true
    else
      kill "$SIM_PID" >/dev/null 2>&1 || true
    fi
    wait "$SIM_PID" 2>/dev/null || true
  fi

  (cd "$SIM_DIR" && docker compose -f compose.simulation.yaml down) || true
  exit "$status"
}

trap 'exit 130' INT TERM
trap cleanup EXIT

require docker
require just
require curl
require python3
docker compose version >/dev/null 2>&1 || die "docker compose plugin not available"

[[ -f "$API_FILE" ]] || die "missing $API_FILE"
[[ -f "$SIM_DIR/justfile" ]] || die "missing $SIM_DIR/justfile (is the submodule initialized?)"
[[ -f "$CLIENT_DIR/main.py" ]] || die "missing $CLIENT_DIR/main.py"

log "Starting simulation..."
if command -v setsid >/dev/null 2>&1; then
  setsid bash -c 'cd "$1" && exec just start-simulation' _ "$SIM_DIR" &
  SIM_STARTED_WITH_SETSID=1
else
  (cd "$SIM_DIR" && exec just start-simulation) &
fi
SIM_PID=$!

log "Starting API container..."
docker compose -f "$API_FILE" up -d api

log "Waiting for API at $API_URL/health ..."
api_ready=0
for _ in $(seq 1 90); do
  if curl -fsS "$API_URL/health" >/dev/null 2>&1; then
    api_ready=1
    break
  fi
  sleep 1
done
if [[ "$api_ready" -ne 1 ]]; then
  docker compose -f "$API_FILE" logs --tail=50 api || true
  die "API did not become healthy at $API_URL within 90s"
fi
log "API is healthy."

if [[ ! -x "$CLIENT_DIR/.venv/bin/python" ]]; then
  log "Creating client virtual environment..."
  python3 -m venv "$CLIENT_DIR/.venv"
  "$CLIENT_DIR/.venv/bin/pip" install --quiet -r "$CLIENT_DIR/requirements.txt"
fi

log "Starting client GUI..."
(cd "$CLIENT_DIR" && "$CLIENT_DIR/.venv/bin/python" main.py)
