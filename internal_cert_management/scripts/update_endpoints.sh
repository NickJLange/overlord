#!/bin/bash

# Script to upload certificates to Vault
# Usage: ./upload-to-vault.sh <hostlist> <subdomain> [vault_cert_algo]
#
# Parameters:
#   hostlist: The target host list (e.g., udm.newyork.nicklange.family)
#   subdomain: The subdomain (e.g., newyork.nicklange.family)
#   vault_cert_algo: Optional certificate algorithm (e.g., rsa2048)

set -e



HOSTLIST=udm.newyork.nicklange.family

types=(ec256)
#types=(rsa2048)

subdomains=(wisconsin miyagi newyork)

# Path to ansible directory
ANSIBLE_PATH="/Users/njl/dev/src/overlord/ansible"

if [ ! -d "$ANSIBLE_PATH" ]; then
    echo "Error: Ansible path not found: $ANSIBLE_PATH"
    exit 1
fi

echo "Reading from Vault to push to $HOSTLIST ($subdomains)..."

cd "$ANSIBLE_PATH"

for subdomain in ${subdomains[@]}
do
    for type in ${types[@]}
    do    # Always run the default playbook (without vault_cert_algo)
        echo "Running default vault update"
        ansible-playbook \
            -e hostlist="$subdomain"_linux \
            -e subdomain="$subdomain".nicklange.family \
            -i non_tasmota_hosts.inventory \
            playbooks/internal_certs_update_endpoints.yml
    done
    if [ "$subdomain" != "miyagi" ]; then
    	ansible-playbook  -e hostlist=udm.$subdomain.nicklange.family -e subdomain=$subdomain.nicklange.family   playbooks/ubiquti-configure-certs.yml
    fi
done
echo "Push completed for $HOSTLIST ($subdomains)"
