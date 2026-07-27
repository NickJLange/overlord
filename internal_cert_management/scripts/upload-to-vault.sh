#!/bin/bash

# Script to upload certificates to Vault
# Usage: ./upload-to-vault.sh [--force]
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
: "${HOSTLIST_VAULT:?HOSTLIST_VAULT is not set}"
: "${SUBDOMAINS_VAULT:?SUBDOMAINS_VAULT is not set}"
: "${CERT_TYPES_VAULT:?CERT_TYPES_VAULT is not set}"
: "${ANSIBLE_PATH:?ANSIBLE_PATH is not set}"
: "${ANSIBLE_INVENTORY:?ANSIBLE_INVENTORY is not set}"
: "${VENV_PATH:?VENV_PATH is not set}"
# UDM vault vars (optional — skip UDM upload if not set)
# SUBDOMAINS_VAULT_UDM and CERT_TYPES_VAULT_UDM

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
read -ra types <<< "$CERT_TYPES_VAULT"
read -ra subdomains <<< "$SUBDOMAINS_VAULT"
read -ra udm_types <<< "${CERT_TYPES_VAULT_UDM:-}"
read -ra udm_subdomains <<< "${SUBDOMAINS_VAULT_UDM:-}"

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

FAILED_RUNS=()

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
            playbooks/internal_certs_update_vault.yml \
            || { echo "⚠️  Failed: $type / $subdomain"; FAILED_RUNS+=("$type/$subdomain"); }
     done
done

# Upload UDM certificates to Vault (if configured)
if [ ${#udm_subdomains[@]} -gt 0 ] && [ -n "${udm_subdomains[0]}" ]; then
    echo ""
    echo "=== Uploading UDM certificates to Vault ==="
    for type in ${udm_types[@]}
    do
        for subdomain in ${udm_subdomains[@]}
        do
            echo "Running UDM vault update: $type / $subdomain"
            ansible-playbook \
                $EXTRA_VARS \
                -e subdomain="$subdomain" \
                -e vault_cert_algo="$type" \
                -i "$ANSIBLE_INVENTORY" \
                playbooks/internal_certs_update_vault.yml \
                || { echo "⚠️  Failed: $type / $subdomain (udm)"; FAILED_RUNS+=("$type/$subdomain"); }
        done
    done
else
    echo "Skipping UDM vault upload (SUBDOMAINS_VAULT_UDM not configured)"
fi

if [ ${#FAILED_RUNS[@]} -gt 0 ]; then
    echo ""
    echo "Vault upload completed with failures:"
    for f in "${FAILED_RUNS[@]}"; do echo "  ✗ $f"; done
    exit 1
else
    echo "Vault upload completed successfully"
fi
