#!/bin/bash

# Script to upload certificates to Vault
# Usage: ./upload-to-vault.sh [--force]
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
: "${HOSTLIST_VAULT:?HOSTLIST_VAULT is not set}"
: "${SUBDOMAINS_VAULT:?SUBDOMAINS_VAULT is not set}"
: "${CERT_TYPES_VAULT:?CERT_TYPES_VAULT is not set}"
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
read -ra types <<< "$CERT_TYPES_VAULT"
read -ra subdomains <<< "$SUBDOMAINS_VAULT"

if [ ! -d "$ANSIBLE_PATH" ]; then
    echo "Error: Ansible path not found: $ANSIBLE_PATH"
    exit 1
fi

echo "Uploading certificates to Vault for $HOSTLIST_VAULT..."
if [ "$FORCE_SKIP_VALIDATION" = true ]; then
    echo "⚠️  Certificate validation is DISABLED (--force)"
fi

cd "$ANSIBLE_PATH"

# Build extra vars for ansible
EXTRA_VARS="-e hostlist=$HOSTLIST_VAULT"
if [ "$FORCE_SKIP_VALIDATION" = true ]; then
    EXTRA_VARS="$EXTRA_VARS -e force_skip_validation=true"
fi

for type in ${types[@]}
do
    for subdomain in ${subdomains[@]}
    do    # Always run the default playbook (without vault_cert_algo)
         echo "Running default vault update"
         ansible-playbook \
            $EXTRA_VARS \
            -e subdomain="$subdomain" \
            -e vault_cert_algo="$type" \
            -i "$ANSIBLE_INVENTORY" \
            playbooks/internal_certs_update_vault.yml
     done
done
echo "Vault upload completed for $HOSTLIST_VAULT"
