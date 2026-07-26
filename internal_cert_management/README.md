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

## Automated Renewal (Systemd Quadlet)

The recommended deployment runs as a daily systemd timer via Podman Quadlet on the target host. All host-specific values come from `.env` — set `DEPLOY_HOST`, `DEPLOY_USER`, and `REPO_PATH` before running any deploy targets.

```bash
# One-time setup: clone repo and install Quadlet units (rootless Podman)
make quadlet-install

# Build the container image on the deploy host
make build

# Manually scp secrets — never committed or scripted
scp .env ${DEPLOY_HOST}:${REPO_PATH}/internal_cert_management/.env
scp etc/lego_secrets.env ${DEPLOY_HOST}:${REPO_PATH}/internal_cert_management/etc/lego_secrets.env

# Verify timer is active
ssh ${DEPLOY_HOST} systemctl --user list-timers cert-renewal
```

The timer fires daily at 03:00, git-pulls the latest repo, and runs `make all` inside the container.

## Manual Usage

To run the full cycle manually:

1. Configure `.env` (copy from `.env.example`)
2. `make all` — renew certs, upload to Vault, push to endpoints

Individual steps:

| Target | Action |
|---|---|
| `make refresh-certs` | Renew certificates via lego |
| `make vault` | Upload certificates to Vault |
| `make certs` | Push certificates to all endpoints (Linux + UDM) |

Note: `ANSIBLE_PATH` should be `/ansible` when running inside the container (bind-mounted from `private-smart-home-ansible`), or the full host path when running locally.
