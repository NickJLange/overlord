#!/bin/bash

# Script to update certificates on Linux endpoints from Vault
# Usage: ./update_linux.sh [--force]
#
# Parameters:
#   --force: Skip SSL certificate validation (for self-signed certs)


# Load configuration from .env file
if [ -f "$(dirname "$0")/../.env" ]; then
    source "$(dirname "$0")/../.env"
else
    echo "Error: .env file not found. Please copy .env.example to .env and configure."
    exit 1
fi

# Validate required variables
: "${SUBDOMAINS_ENDPOINTS:?SUBDOMAINS_ENDPOINTS is not set}"
: "${CERT_TYPES_ENDPOINTS:?CERT_TYPES_ENDPOINTS is not set}"
: "${DOMAIN_SUFFIX:?DOMAIN_SUFFIX is not set}"
: "${ANSIBLE_PATH:?ANSIBLE_PATH is not set}"
: "${ANSIBLE_INVENTORY:?ANSIBLE_INVENTORY is not set}"
: "${VENV_PATH:?VENV_PATH is not set}"
# LINUX_HOSTS_EXCLUDE — optional space-separated list of hosts to skip (e.g. "terraAlpha lunarBeacon")

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
read -ra types <<< "$CERT_TYPES_ENDPOINTS"
read -ra subdomains <<< "$SUBDOMAINS_ENDPOINTS"

if [ ! -d "$ANSIBLE_PATH" ]; then
    echo "Error: Ansible path not found: $ANSIBLE_PATH"
    exit 1
fi

echo "Reading from Vault to push to Linux endpoints..."
if [ "$FORCE_SKIP_VALIDATION" = true ]; then
    echo "⚠️  Certificate validation is DISABLED (--force)"
fi

# Build extra vars for ansible
EXTRA_VARS=""
if [ "$FORCE_SKIP_VALIDATION" = true ]; then
    EXTRA_VARS="-e force_skip_validation=true"
fi

FAILED_RUNS=()

for subdomain in "${subdomains[@]}"
do
    cd "$ANSIBLE_PATH" || exit 1
    # Build --limit: start with the group, append :!host for each excluded host
    LIMIT="${subdomain}_linux"
    for excluded in ${LINUX_HOSTS_EXCLUDE:-}; do
        LIMIT="${LIMIT}:!${excluded}"
    done

    for type in "${types[@]}"
    do
        ansible-playbook \
            $EXTRA_VARS \
            --limit "$LIMIT" \
            -e hostlist="${subdomain}_linux" \
            -e subdomain="${subdomain}.${DOMAIN_SUFFIX}" \
            -e vault_cert_algo="$type" \
            -i "$ANSIBLE_INVENTORY" \
            playbooks/internal_certs_update_endpoints.yml \
            || { echo "⚠️  Failed: $type / $subdomain (linux)"; FAILED_RUNS+=("$type/${subdomain}_linux"); }
    done
done

if [ ${#FAILED_RUNS[@]} -gt 0 ]; then
    echo "Linux push completed with failures:"
    for f in "${FAILED_RUNS[@]}"; do echo "  ✗ $f"; done
    exit 1
else
    echo "Linux push completed successfully"
fi
