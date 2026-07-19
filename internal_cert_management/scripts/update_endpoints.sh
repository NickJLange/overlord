#!/bin/bash

# Script to update certificates on all endpoints (Linux + UDM) from Vault
# Delegates to update_linux.sh and update_udm.sh
#
# Usage: ./update_endpoints.sh [--force]
#
# Parameters:
#   --force: Skip SSL certificate validation (for self-signed certs)

SCRIPT_DIR="$(dirname "$0")"

FAILED=0

echo "=== Updating Linux endpoints ==="
"$SCRIPT_DIR/update_linux.sh" "$@" || FAILED=1

echo ""
echo "=== Updating UDM devices ==="
"$SCRIPT_DIR/update_udm.sh" "$@" || FAILED=1

if [ $FAILED -ne 0 ]; then
    echo ""
    echo "One or more endpoint updates failed."
    exit 1
fi
