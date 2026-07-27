#!/bin/bash

# Script to update certificates on Ubiquiti UDM devices from Vault
# Usage: ./update_udm.sh [--force]
#
# Parameters:
#   --force: Skip SSL certificate validation (for self-signed certs)
#
# Note: Subdomains listed in SUBDOMAINS_UDM_EXCLUDE are skipped (e.g. sites without a UDM).


# Load configuration from .env file
if [ -f "$(dirname "$0")/../.env" ]; then
    source "$(dirname "$0")/../.env"
else
    echo "Error: .env file not found. Please copy .env.example to .env and configure."
    exit 1
fi

# Validate required variables
: "${SUBDOMAINS_ENDPOINTS:?SUBDOMAINS_ENDPOINTS is not set}"
: "${DOMAIN_SUFFIX:?DOMAIN_SUFFIX is not set}"
: "${ANSIBLE_PATH:?ANSIBLE_PATH is not set}"
: "${ANSIBLE_INVENTORY:?ANSIBLE_INVENTORY is not set}"
: "${VENV_PATH:?VENV_PATH is not set}"

# Activate Python virtual environment if available (skipped inside container where packages are global)
if [ -n "${VENV_PATH}" ] && [ -f "${VENV_PATH}/bin/activate" ]; then
    source "${VENV_PATH}/bin/activate"
fi

# Parse command line arguments
FORCE_SKIP_VALIDATION=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE_SKIP_VALIDATION=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--force]"
            echo "  --force: Skip SSL certificate validation"
            exit 1
            ;;
    esac
done

# Convert space-separated strings to arrays
read -ra subdomains <<< "$SUBDOMAINS_ENDPOINTS"
read -ra excludes <<< "${SUBDOMAINS_UDM_EXCLUDE:-}"

if [ ! -d "$ANSIBLE_PATH" ]; then
    echo "Error: Ansible path not found: $ANSIBLE_PATH"
    exit 1
fi

echo "Reading from Vault to push to UDM devices..."
if [ "$FORCE_SKIP_VALIDATION" = true ]; then
    echo "⚠️  Certificate validation is DISABLED (--force)"
fi

# Build extra vars for ansible
EXTRA_VARS=""
if [ "$FORCE_SKIP_VALIDATION" = true ]; then
    EXTRA_VARS="-e force_skip_validation=true"
fi

# Check if a subdomain is in the exclude list
is_excluded() {
    local subdomain="$1"
    for excluded in "${excludes[@]}"; do
        if [ "$subdomain" = "$excluded" ]; then
            return 0
        fi
    done
    return 1
}

FAILED_RUNS=()

for subdomain in ${subdomains[@]}
do
    if is_excluded "$subdomain"; then
        echo "Skipping UDM for $subdomain (excluded via SUBDOMAINS_UDM_EXCLUDE)"
        continue
    fi

    cd "$ANSIBLE_PATH" || exit 1
    ansible-playbook \
        $EXTRA_VARS \
        -e hostlist="udm.${subdomain}.${DOMAIN_SUFFIX}" \
        -e subdomain="udm.${subdomain}.${DOMAIN_SUFFIX}" \
        -i "$ANSIBLE_INVENTORY" \
        playbooks/ubiquti-configure-certs.yml \
        || { echo "⚠️  Failed: udm.$subdomain (ubiquiti)"; FAILED_RUNS+=("udm.$subdomain"); }
done

if [ ${#FAILED_RUNS[@]} -gt 0 ]; then
    echo "UDM push completed with failures:"
    for f in "${FAILED_RUNS[@]}"; do echo "  ✗ $f"; done
    exit 1
else
    echo "UDM push completed successfully"
fi
