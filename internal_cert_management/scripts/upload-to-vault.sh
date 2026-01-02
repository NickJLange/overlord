#!/bin/bash

# Script to upload certificates to Vault
# Usage: ./upload-to-vault.sh <hostlist> <subdomain> [vault_cert_algo]
#
# Parameters:
#   hostlist: The target host list (e.g., udm.newyork.nicklange.family)
#   subdomain: The subdomain (e.g., newyork.nicklange.family)
#   vault_cert_algo: Optional certificate algorithm (e.g., rsa2048)

set -e

if [ $# -lt 0 ]; then
    echo "Usage: $0 <hostlist> <subdomain> [vault_cert_algo]"
    echo "Example: $0 udm.newyork.nicklange.family newyork.nicklange.family rsa2048"
    exit 1
fi


HOSTLIST=udm.newyork.nicklange.family
VAULT_CERT_ALGO=${3:-"rsa2048"}

types=(rsa2048 ec256)
#types=(rsa2048)

subdomains=(newyork.nicklange.family wisconsin.nicklange.family miyagi.nicklange.family)

# Path to ansible directory
ANSIBLE_PATH="/Users/njl/dev/src/overlord/ansible"

if [ ! -d "$ANSIBLE_PATH" ]; then
    echo "Error: Ansible path not found: $ANSIBLE_PATH"
    exit 1
fi

echo "Uploading certificates to Vault for $HOSTLIST ($SUBDOMAIN)..."

cd "$ANSIBLE_PATH"

for type in ${types[@]}
do
    for subdomain in ${subdomains[@]}
    do    # Always run the default playbook (without vault_cert_algo)
        echo "Running default vault update"
        ansible-playbook \
            -e hostlist="$HOSTLIST" \
            -e subdomain="$subdomain" \
            -e vault_cert_algo="$type" \
            -i non_tasmota_hosts.inventory \
            playbooks/internal_certs_update_vault.yml
    done
done
echo "Vault upload completed for $HOSTLIST ($subdomains)"
