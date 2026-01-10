#!/bin/bash

# Script to update certificates on endpoints from Vault
# Usage: ./update_endpoints.sh [--force]
#
# Parameters:
#   --force: Skip SSL certificate validation (for self-signed certs)

set -e

# Load configuration from .env file
if [ -f "$(dirname "$0")/../.env" ]; then
    source "$(dirname "$0")/../.env"
else
    echo "Error: .env file not found. Please copy .env.example to .env and configure."
    exit 1
fi

# Validate required variables
: "${HOSTLIST_ENDPOINTS:?HOSTLIST_ENDPOINTS is not set}"
: "${SUBDOMAINS_ENDPOINTS:?SUBDOMAINS_ENDPOINTS is not set}"
: "${CERT_TYPES_ENDPOINTS:?CERT_TYPES_ENDPOINTS is not set}"
: "${DOMAIN_SUFFIX:?DOMAIN_SUFFIX is not set}"
: "${ANSIBLE_PATH:?ANSIBLE_PATH is not set}"
: "${ANSIBLE_INVENTORY:?ANSIBLE_INVENTORY is not set}"

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

echo "Reading from Vault to push to endpoints..."
if [ "$FORCE_SKIP_VALIDATION" = true ]; then
    echo "⚠️  Certificate validation is DISABLED (--force)"
fi

cd "$ANSIBLE_PATH"

# Build extra vars for ansible
EXTRA_VARS=""
if [ "$FORCE_SKIP_VALIDATION" = true ]; then
    EXTRA_VARS="-e force_skip_validation=true"
fi

for subdomain in ${subdomains[@]}
do
    for type in ${types[@]}
    do    # Deploy certificate for endpoint
         ansible-playbook \
             $EXTRA_VARS \
             -e hostlist="${subdomain}_linux" \
             -e subdomain="${subdomain}.${DOMAIN_SUFFIX}" \
             -i "$ANSIBLE_INVENTORY" \
             playbooks/internal_certs_update_endpoints.yml
     done
     if [ "$subdomain" != "miyagi" ]; then
     	ansible-playbook $EXTRA_VARS -e hostlist="udm.${subdomain}.${DOMAIN_SUFFIX}" -e subdomain="${subdomain}.${DOMAIN_SUFFIX}" playbooks/ubiquiti-configure-certs.yml
     fi
done
echo "Push completed for endpoints"
