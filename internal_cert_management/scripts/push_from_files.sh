#!/bin/bash

# Script to push certificates from local lego-data/ directly to the Vault host
# and signal the Vault Podman container to reload TLS certs via SIGHUP.
#
# Use this when the normal lego → Vault upload workflow is unavailable
# (e.g. offline certs that need to be placed on the Vault host directly).
#
# Usage: ./push_from_files.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load configuration from .env file
if [ -f "$SCRIPT_DIR/../.env" ]; then
    source "$SCRIPT_DIR/../.env"
else
    echo "Error: .env file not found. Please copy .env.example to .env and configure."
    exit 1
fi

# Validate required variables
: "${HOSTLIST_VAULT:?HOSTLIST_VAULT is not set}"
: "${SUBDOMAIN_VAULT_HOST:?SUBDOMAIN_VAULT_HOST is not set}"
: "${CERT_TYPE_VAULT_HOST:?CERT_TYPE_VAULT_HOST is not set}"
: "${ANSIBLE_PATH:?ANSIBLE_PATH is not set}"
: "${ANSIBLE_INVENTORY:?ANSIBLE_INVENTORY is not set}"
: "${VENV_PATH:?VENV_PATH is not set}"

# Activate Python virtual environment if available (skipped inside container where packages are global)
if [ -n "${VENV_PATH}" ] && [ -f "${VENV_PATH}/bin/activate" ]; then
    source "${VENV_PATH}/bin/activate"
fi

if [ ! -d "$ANSIBLE_PATH" ]; then
    echo "Error: Ansible path not found: $ANSIBLE_PATH"
    exit 1
fi

LEGO_DATA_DIR="$SCRIPT_DIR/../lego-data"

echo "Pushing certs from local files to Vault host ($HOSTLIST_VAULT) for $SUBDOMAIN_VAULT_HOST ($CERT_TYPE_VAULT_HOST)..."

EXTRA_VARS="-e hostlist=$HOSTLIST_VAULT"

# Ansible expects cert files under a subdirectory matching the domain and key type.
# Actual lego layout: lego-data/certificates/<domain>.*  (flat, not nested by type).
# Adjust SUBDOMAIN_VAULT_HOST/CERT_TYPE_VAULT_HOST in .env to match your lego-data layout.
cert_source_dir="$(cd "$LEGO_DATA_DIR/${SUBDOMAIN_VAULT_HOST}/${CERT_TYPE_VAULT_HOST}" 2>/dev/null && pwd)"
if [ -z "$cert_source_dir" ]; then
    echo "Error: Cert source dir not found: ${LEGO_DATA_DIR}/${SUBDOMAIN_VAULT_HOST}/${CERT_TYPE_VAULT_HOST}"
    exit 1
fi

cd "$ANSIBLE_PATH" || exit 1
ansible-playbook \
    $EXTRA_VARS \
    -e subdomain="$SUBDOMAIN_VAULT_HOST" \
    -e vault_cert_algo="$CERT_TYPE_VAULT_HOST" \
    -e cert_source_dir="$cert_source_dir" \
    -i "$ANSIBLE_INVENTORY" \
    playbooks/internal_certs_push_from_files.yml \
    || { echo "  ✗ push-from-files failed for $CERT_TYPE_VAULT_HOST/$SUBDOMAIN_VAULT_HOST"; exit 1; }

echo "Push-from-files completed successfully"
echo "Note: if the Vault container was not running, start it manually — certs are in place."
