# AGENTS.md

> [!IMPORTANT]
> This project follows the official [AI Agent Standards](file:///Users/njl/dev/standards/README.md). All agents MUST adhere to the [Spec-Driven Development workflow](file:///Users/njl/dev/standards/AGENT_WORKFLOW.md) for non-trivial tasks.

This file provides context and guidance for AI Agents working within the **Overlord** repository.

## Project Overview

**Overlord** is a collection of network scripts and configuration management tools for a home network infrastructure. It is designed to automate tasks that would otherwise be handled by paid services or manual intervention.

### Key Components

*   **Internal Certificate Management (Gemini Project)**:
    *   **Location:** `internal_cert_management/`
    *   **Purpose:** Automates the renewal and deployment of internal TLS certificates using Let's Encrypt (DNS-01 challenge), HashiCorp Vault, and Ansible.
    *   **Key Files:**
        *   `scripts/lego.sh`: Renews certificates using Lego.
        *   `scripts/upload-to-vault.sh`: Uploads certificates to Vault.
        *   `README.md`: Documentation for this subsystem.

## Repository Structure

*   **`internal_cert_management/`**: Subproject for DNS and TLS certificate handling.
*   **`bin/`**: General utility scripts.
*   **`data/`** & **`data_pipeline/`**: Data storage and processing scripts.
*   **`network_kill_switch/`**: Emergency network controls (git submodule).
*   **`private-smart-home-ansible/`**: Ansible roles for smart home devices (git submodule).
*   **`bpf_tcp_monitor/`**: BPF-based network monitoring tools.

## Active Tasks / Jira Context

The following Jira tasks are currently relevant to this repository:

| Jira Key | Summary | Context |
| :--- | :--- | :--- |
| **HOMETECH-29** | Add Zigbee device monitoring alerts | While primarily in `mkrasberry`, this may involve data pipelines or monitoring dashboards in `overlord`. |
| **HOMETECH-17** | Lock down SSH ports / user-access | May involve scripts in `bin/` or `network_kill_switch/` for emergency access or locking. |

## Development Guidelines

1.  **Security First**: Never commit secrets. Use `.env` files (gitignored) based on `.example.env` templates.
2.  **Idempotency**: Ensure scripts and playbooks can be run multiple times without adverse effects.
