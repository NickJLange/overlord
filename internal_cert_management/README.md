# Internal DNS Management

This subproject manages the renewal and deployment of internal TLS certificates using Let's Encrypt, Vault, and Ansible.

## Workflow

The process of renewing and deploying certificates is as follows:

https://sven.stormbind.net/blog/posts/misc_nftp_masquarading/
Add the iptables rule for 10.0.0.0/8 -> eth0 until we can find something smoother.

1.  **Renew Certificates:** The `scripts/lego.sh` script is executed to renew wildcard TLS certificates from Let's Encrypt using the DNS-01 challenge. This script utilizes Lego to automate the certificate acquisition process.

2.  **Upload to Vault:** After the certificates are renewed, the `private-smart-home-ansible/playbooks/internal_certs_update_vault.yml` Ansible playbook is run. This playbook uploads the newly obtained certificates to a Vault KV store for secure storage.

`ansible-playbook -e subdomain=miyagi.nicklange.family -e hostlist=terraDelta -i non_tasmota_hosts.inventory playbooks/internal_certs_update_vault.yml`

3.  **Push to Endpoints:** Finally, the `private-smart-home-ansible/playbooks/internal_certs_update_endpoints.yml` Ansible playbook is executed. This playbook retrieves the certificates from Vault and pushes them to the designated endpoints, ensuring that all services are using the latest TLS certificates.

`ansible-playbook -e subdomain=newyork.nicklange.family -e hostlist=newyork_linux playbooks/internal_certs_update_endpoints.yml`

## Key Components

*   **Lego:** A Let's Encrypt client and ACME library that simplifies the process of obtaining and renewing TLS certificates.
*   **Vault:** A tool for securely storing and accessing secrets, in this case, the TLS certificates.
*   **Ansible:** An automation engine used to orchestrate the uploading of certificates to Vault and their deployment to endpoints.

## Configuration

The `scripts/lego.sh` script requires a `.env` file in the `internal_dns_management` directory with the following variables:

*   `LEGO_EMAIL`: The email address to use for Let's Encrypt.
*   `LEGO_DNS_PROVIDER`: The DNS provider to use for the DNS-01 challenge.
*   `VAULT_ADDR`: The address of the Vault server.
*   `VAULT_TOKEN`: The Vault token to use for authentication.

The script also uses a `domains.txt` file in the `internal_dns_management/etc` directory to get the list of domains to renew.

## Playbook Variables

The Ansible playbooks use the following extra variables:

*   `subdomain`: The subdomain for which the certificate is being deployed.
*   `hostlist`: A comma-separated list of hosts to which the certificate should be deployed.

## Usage

To initiate the certificate renewal and deployment process, execute the scripts and playbooks in the order described in the Workflow section. Ensure that Lego, Vault, and Ansible are properly configured and accessible from the environment where the scripts are being run.
