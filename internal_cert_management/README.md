# Internal DNS Management

This subproject manages the renewal and deployment of internal TLS certificates using Let's Encrypt, Vault, and Ansible.

## Workflow

The process of renewing and deploying certificates is as follows:

1.  **Renew Certificates:** The `scripts/lego.sh` script is executed to renew wildcard TLS certificates from Let's Encrypt using the DNS-01 challenge. This script utilizes Lego to automate the certificate acquisition process.

2.  **Upload to Vault:** After the certificates are renewed, the `private-smart-home-ansible/playbooks/internal_certs_update_vault.yml` Ansible playbook is run. This playbook uploads the newly obtained certificates to a Vault KV store for secure storage.

3.  **Push to Endpoints:** Finally, the `private-smart-home-ansible/playbooks/internal_certs_update_endpoints.yml` Ansible playbook is executed. This playbook retrieves the certificates from Vault and pushes them to the designated endpoints, ensuring that all services are using the latest TLS certificates.

## Key Components

*   **Lego:** A Let's Encrypt client and ACME library that simplifies the process of obtaining and renewing TLS certificates.
*   **Vault:** A tool for securely storing and accessing secrets, in this case, the TLS certificates.
*   **Ansible:** An automation engine used to orchestrate the uploading of certificates to Vault and their deployment to endpoints.

## Configuration

All scripts require a `.env` file in the root directory. Copy `.env.example` to `.env` and update with your environment-specific values:

```bash
cp .env.example .env
# Edit .env with your values
```

Required environment variables:

*   **Lego:** `ADMIN_EMAIL`, `LEGO_DNS_PROVIDER`, `LEGO_DNS_RESOLVERS`
*   **Subdomains:** `SUBDOMAINS_EC256`, `SUBDOMAINS_RSA2048`, `SUBDOMAINS_VAULT`, `SUBDOMAINS_ENDPOINTS`
*   **Hosts:** `HOSTLIST_VAULT`, `HOSTLIST_ENDPOINTS`
*   **Ansible:** `ANSIBLE_PATH`, `ANSIBLE_INVENTORY`
*   **Cert Types:** `CERT_TYPES_VAULT`, `CERT_TYPES_ENDPOINTS`

See `.env.example` for detailed descriptions of each variable.

## Usage

To initiate the certificate renewal and deployment process:

1. Configure `.env` with your environment-specific values
2. Execute `make refresh-certs` to renew certificates
3. Execute `make vault` to upload certificates to Vault
4. Execute `make certs` to deploy certificates to endpoints

See `Makefile` for additional targets and options.
