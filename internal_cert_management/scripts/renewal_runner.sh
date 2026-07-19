#!/usr/bin/env bash
set -euo pipefail

WORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="/var/log/cert_management"
LOCKFILE="/var/run/cert_renewal.lock"

mkdir -p "$LOG_DIR"
LOGFILE="$LOG_DIR/renewal-$(date +%Y%m%d-%H%M%S).log"

exec 9>"$LOCKFILE"
flock -n 9 || { echo "cert renewal already running, exiting"; exit 1; }

{
    echo "=== cert renewal started: $(date) ==="
    cd "$WORK_DIR"
    make all
    echo "=== cert renewal completed: $(date) ==="
} 2>&1 | tee "$LOGFILE"

# Keep last 10 logs
ls -t "$LOG_DIR"/renewal-*.log 2>/dev/null | tail -n +11 | xargs rm -f || true
