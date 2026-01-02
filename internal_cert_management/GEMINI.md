# Gemini Project: Internal DNS Management

This project manages internal DNS and TLS certificates using Let's Encrypt and Vault.

## Key Components:

- **Lego:** Acquires TLS certificates from Let's Encrypt using DNS-01 challenge.
- **Vault:** Stores the obtained TLS certificates securely.
- **Ansible:** Automates the process of uploading certificates to Vault.
- **Shell Scripts:** Orchestrate the certificate renewal and deployment process.

## Workflow:

1.  **Renew Certificates:** A script (`scripts/lego.sh`) uses Lego to renew wildcard certificates for various subdomains.
2.  **Upload to Vault:** An Ansible playbook uploads the renewed certificates to a Vault KV store.
3.  **Push to Endpoints:** A script pushes the certificates from Vault to the designated endpoints.
