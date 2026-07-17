# Gemini Project: Internal DNS Management

## Engineering Preferences

These preferences shape all work on this project. Apply them before any other consideration.

- **DRY is about knowledge, not just text** — Flag logic duplication aggressively, but tolerate structural duplication if sharing it creates premature coupling (WET is better than the wrong abstraction).
- **Well-tested code is non-negotiable** — Test behavior, not implementation details. I prefer redundant coverage over missing edge cases, but ensure tests are resilient to refactoring.
- **Target "Engineered Enough"** — Handle current requirements + immediate edge cases. **Apply YAGNI**: do not build for hypothetical future use cases. Abstract only when you see the pattern for the third time (Rule of Three).
- **Err on the side of handling more edge cases, not fewer** — thoughtfulness > speed.
- **Bias toward explicit over clever.**

---

## Review Process (Plan Mode)

Before starting a review, you **MUST** ask:

> **BIG CHANGE or SMALL CHANGE?**
> 1. **BIG CHANGE**: Work through this interactively, one section at a time (Architecture → Code Quality → Tests → Performance) with at most 4 top issues in each section.
> 2. **SMALL CHANGE**: Work through interactively ONE question per review section.

### Review Sections

Walk through these four sections **in order**, presenting one section at a time. Wait for user feedback before proceeding to the next.

1. **Architecture review** — overall system design, component boundaries, dependency graph, coupling, data flow, scaling, security.
2. **Code quality review** — organization, module structure, DRY violations, error handling patterns, missing edge cases, tech debt hotspots, and over/under-engineering relative to preferences.
3. **Test review** — coverage gaps (unit, integration, e2e), test quality, assertion strength, missing edge cases, untested failure modes, and error paths.
4. **Performance review** — N+1 queries, database access patterns, memory-usage concerns, caching opportunities, slow or high-complexity code paths.

### Issue Format

For every specific issue (bug, smell, design concern, or risk):

- Describe the problem concretely, with file and line references.
- Present 2-3 options, including "do nothing" where reasonable.
- For each option, specify: implementation effort, risk, impact on other code, and **maintenance burden**.
- Give an opinionated recommendation and why, mapped to the engineering preferences.
- Explicitly ask whether the user agrees or wants a different direction before proceeding.

**Formatting Rules**:
- **NUMBER issues** (1, 2, 3...) and then give **LETTERS for options** (A, B, C...).
- The recommended option must always be the 1st option (Option A).
- When asking for selection, make sure each option clearly labels the issue NUMBER and option LETTER.

---

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
│   ├── push_from_files.sh   # Push local lego-data/ certs directly to Vault host (bypass)
│   ├── update_endpoints.sh  # Thin wrapper: delegates to update_linux.sh + update_udm.sh
│   ├── update_linux.sh      # Deploy certificates to Linux endpoints from Vault
│   ├── update_udm.sh        # Deploy certificates to Ubiquiti UDM devices from Vault
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

3.  **Push to Endpoints:** `scripts/update_endpoints.sh` is a thin wrapper that delegates to:
   - `update_linux.sh` — retrieves certs from Vault, runs `internal_certs_update_endpoints.yml` for Linux hosts
   - `update_udm.sh` — retrieves certs from Vault, runs `ubiquti-configure-certs.yml` for Ubiquiti devices (skips hosts in `SUBDOMAINS_UDM_EXCLUDE`)
   - Both sub-scripts activate the Python venv (`VENV_PATH`) for hvac access
   - Failures in either script are aggregated; both always run regardless of the other's result

4.  **Bypass (Offline):** `scripts/push_from_files.sh` pushes certs directly from `lego-data/` to the Vault host filesystem and signals the Vault Podman container via SIGHUP to reload TLS. Use when the normal Vault KV upload path is unavailable.

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

# 4. Merge with fast-forward merge
git checkout main
git pull origin main
git merge --ff-only feature/branch-name
git push origin main
```

**Key Steps:**
- Squash commits maintain clean history
- Use `--force-with-lease` for safety
- Verify PR reflects squashed changes before final merge
- Use fast-forward merge after feature branch is squashed and up-to-date with main

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
