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

The timer is scheduled daily at 03:00 with a randomized delay of up to 30 minutes.
Before building, it fast-forwards the deployed checkout's current branch from its
configured upstream, then initializes `private-smart-home-ansible` and its nested
submodules at the revisions pinned by their parents. Those revisions can include
unmerged feature-branch commits; other branch tips and edits on other machines
are not automatically copied to the deployed checkout.

The container bind-mounts that checkout and runs `make all`. Neither the timer nor
`make quadlet-install` enforces a branch or a clean worktree: non-conflicting local
edits can survive `git pull --ff-only` and be used by the container. Keep the deployed
checkout on the intended production branch and inspect local source changes before
running it. No automatic reset discards local edits.

`make quadlet-install` also updates the checkout before rendering its unit templates.
Re-run that target after changes to the installed Quadlet units (a source pull alone
does not update them).

## Validation

From this directory, run the isolated script/installation regressions and existing
configuration checks without contacting production:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
bash tests/test-env-loading.sh
```

The Ansible submodule also provides `tests/test-cert-install-identity.sh` for a
real Vault/controller/SSH-endpoint test using disposable Podman containers and
generated certificates. For a local ARM validation run, build the controller from
this directory and run the test from the repository root:

```bash
podman build --build-arg LEGO_ARCH=arm64 -t localhost/cert-renewal-test .
(cd .. && CONTROLLER_IMAGE=localhost/cert-renewal-test bash private-smart-home-ansible/tests/test-cert-install-identity.sh)
```

Use `--build-arg LEGO_ARCH=amd64` for an x86-64 controller. The remote deployment
`make build` target and installed Quadlet build unit explicitly target `amd64`;
setting a shell variable alone does not override their build arguments. The test
covers administrative installation, direct `certpush` rotation without sudo,
backups and service links, including an endpoint that cannot reach Vault.

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
