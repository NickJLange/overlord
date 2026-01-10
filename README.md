# Network Overlord

A series of scripts for my home network to help avoid paying to other people to do the same thing...

## Table of Contents
- [Security Best Practices](#security-best-practices)
- [Key Components](#key-components)

## Key Components

- **[Internal Certificate Management (`internal_cert_management`)](./internal_cert_management/README.md)**: Also known as the "Gemini Project", helps manage internal DNS and TLS certificates.


## Security Best Practices

To maintain security when working with this repository:

1. **Never commit credentials or secrets**:
   - Use the example template files (*.example.env) for configuration
   - Copy them to actual files (*.env) for local use, which are gitignored
   - Keep secrets in environment variables or secret management systems

2. **Sensitive Data**:
   - MAC address databases, internal domain information, and network configurations should not be committed
   - Firmware files and binaries should be downloaded from their original sources

3. **Setting Up**:
   - Check `.gitignore` to see which files are excluded from version control
   - Create your own environment files based on the example templates
   - Use vault or other secure storage for certificates and credentials
