# Gemini Project: Internal DNS Management

This project manages internal DNS and TLS certificates using Let's Encrypt and Vault.

## Project Structure

```
internal_cert_management/
├── .env.example              # Configuration template (copy to .env)
├── .gitignore                # Git ignore rules
├── Makefile                  # Build targets
├── README.md                 # User documentation
├── AGENTS.md                 # This file
├── Containerfile             # Container definition
├── etc/
│   └── lego_secrets.env      # Lego DNS provider secrets (not in repo)
├── lego-data/                # Generated certificate data
├── scripts/
│   ├── lego.sh              # Renew certificates from Let's Encrypt
│   ├── upload-to-vault.sh   # Upload certificates to Vault
│   ├── update_endpoints.sh  # Deploy certificates to endpoints
│   └── update_internal_dns.sh  # Legacy DNS update script
```

## Key Components

- **Lego:** Acquires TLS certificates from Let's Encrypt using DNS-01 challenge.
- **Vault:** Stores the obtained TLS certificates securely.
- **Ansible:** Automates the process of uploading certificates to Vault and deploying to endpoints.
- **Shell Scripts:** Orchestrate the certificate renewal and deployment process.

## Workflow

1.  **Renew Certificates:** `scripts/lego.sh` uses Lego to renew wildcard certificates for various subdomains.
   - Reads subdomains from `.env` (`SUBDOMAINS_EC256`, `SUBDOMAINS_RSA2048`)
   - Executes Lego in Podman with DNS provider credentials
   - Stores renewed certificates in `lego-data/`

2.  **Upload to Vault:** `scripts/upload-to-vault.sh` uploads renewed certificates to Vault.
   - Runs Ansible playbook `internal_certs_update_vault.yml`
   - Encrypts and stores certificates in Vault KV store
   - Uses credentials from `.env` (`ANSIBLE_PATH`, `ANSIBLE_INVENTORY`)

3.  **Push to Endpoints:** `scripts/update_endpoints.sh` deploys certificates from Vault to endpoints.
   - Retrieves certificates from Vault
   - Runs Ansible playbook `internal_certs_update_endpoints.yml`
   - Applies certificates to designated hosts
   - Also updates Ubiquiti devices with `ubiquti-configure-certs.yml`

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      CERTIFICATE RENEWAL FLOW                   │
└─────────────────────────────────────────────────────────────────┘

                            Let's Encrypt
                                  │
                                  │ DNS-01 Challenge
                                  │
                    ┌─────────────▼─────────────┐
                    │    scripts/lego.sh        │
                    │ (Runs in Podman)          │
                    │ - Reads SUBDOMAINS_EC256  │
                    │ - Reads SUBDOMAINS_RSA2048│
                    └─────────────┬─────────────┘
                                  │
                                  │ Renewed Certificates
                                  │
                    ┌─────────────▼──────────────┐
                    │   lego-data/ directory    │
                    │ (EC256 & RSA2048 certs)   │
                    └─────────────┬──────────────┘
                                  │
                                  │
        ┌─────────────────────────┴─────────────────────────┐
        │                                                   │
        │ Parallel Paths:                                   │
        │                                                   │
    ┌───▼────────────────────┐          ┌──────────────────▼────┐
    │ upload-to-vault.sh     │          │ update_endpoints.sh   │
    │                        │          │                       │
    │ ┌────────────────────┐ │          │ ┌──────────────────┐  │
    │ │ Ansible Playbook: │ │          │ │ Ansible Playbooks:
    │ │ internal_certs_   │ │          │ │ - internal_certs_ │  │
    │ │ update_vault.yml  │ │          │ │   update_endpoints│  │
    │ └────────────────────┘ │          │ │ - ubiquti-       │  │
    │         │              │          │ │   configure-certs│  │
    │         │              │          │ │                  │  │
    └─────────┼──────────────┘          └──────┼─────────────┘
              │                                │
              │ Encrypted Storage             │ Certificate Deployment
              │                                │
         ┌────▼──────────┐            ┌────────▼──────────┐
         │  HashiCorp    │            │  Target Endpoints │
         │   Vault       │            │ (Linux Hosts +    │
         │ KV Store      │            │  Ubiquiti devices)│
         └───────────────┘            └───────────────────┘
```

## PR Workflow

### After Review Approval & Before Merge

Once reviewers approve all commits, execute the final workflow ritual:

```bash
# 1. Squash all commits into single logical commit
git rebase -i origin/main  # Or target branch

# 2. Force push to PR branch
git push origin feature/branch-name --force-with-lease

# 3. Verify PR updates with squashed commit
# (GitHub will auto-update the PR)

# 4. Merge with rebase strategy
git checkout main
git pull origin main
git rebase feature/branch-name
git push origin main
```

**Key Steps:**
- Squash commits maintain clean history
- Use `--force-with-lease` for safety
- Verify PR reflects squashed changes before final merge
- Use rebase merge (not squash merge) to preserve squashed commit

---

## Pre-Commit Checklist (Required Before Push)

Before submitting a feature branch for merge, verify the following:

### 1. Security & Configuration
- [ ] No hardcoded PII, domains, IP addresses, or paths in scripts
- [ ] All environment-specific values moved to `.env` files (gitignored)
- [ ] Sensitive data referenced via environment variables or config files only
- [ ] Verify `.env.example` template is up-to-date with required variables

### 2. Documentation & Architecture
- [ ] README.md is updated and accurate
- [ ] AGENTS.md reflects current project structure and workflows
- [ ] All code comments are current and accurate
- [ ] Architecture diagrams updated (if applicable)
- [ ] No stray or outdated content in documentation files

### 3. Testing & Validation
- [ ] All shell scripts pass syntax validation (`bash -n script.sh`)
- [ ] Script execution paths and dependencies verified
- [ ] Ansible playbook references are valid
- [ ] Manual testing of key workflows completed
- [ ] No broken or commented-out test cases

### How to Run Pre-Commit Checks

```bash
# Validate shell scripts
for script in scripts/*.sh; do bash -n "$script" && echo "✓ $script"; done

# Check for hardcoded values (example patterns)
grep -r "nicklange.family\|/Users/njl\|10\.0\." scripts/ README.md AGENTS.md || echo "✓ No obvious hardcoded values"

# Review documentation
echo "✓ Verify README.md and AGENTS.md are up-to-date"
```
