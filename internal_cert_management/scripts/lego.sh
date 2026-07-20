#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load configuration from .env file
if [ -f "$WORK_DIR/.env" ]; then
    source "$WORK_DIR/.env"
else
    echo "Error: .env file not found. Please copy .env.example to .env and configure."
    exit 1
fi

# Validate required variables
: "${ADMIN_EMAIL:?ADMIN_EMAIL is not set}"
: "${SUBDOMAINS_EC256:?SUBDOMAINS_EC256 is not set}"
: "${SUBDOMAINS_RSA2048:?SUBDOMAINS_RSA2048 is not set}"

# DNS provider credentials come from etc/lego_secrets.env, injected by the
# Quadlet EnvironmentFile= — no --env-file needed here.

LEGO_DATA_DIR="$WORK_DIR/lego-data"
mkdir -p "$LEGO_DATA_DIR"

read -ra subdomains_ec256 <<< "$SUBDOMAINS_EC256"
read -ra subdomains_rsa2048 <<< "$SUBDOMAINS_RSA2048"

for subdomain in "${subdomains_ec256[@]}"; do
    echo "Renewing ec256 cert for $subdomain"
    lego \
        --path "$LEGO_DATA_DIR" \
        --email "$ADMIN_EMAIL" \
        --key-type ec256 \
        --dns "$LEGO_DNS_PROVIDER" \
        --dns.resolvers "$LEGO_DNS_RESOLVERS" \
        --domains "*.$subdomain" \
        --domains "$subdomain" \
        renew
done

for subdomain in "${subdomains_rsa2048[@]}"; do
    echo "Renewing rsa2048 cert for $subdomain"
    lego \
        --path "$LEGO_DATA_DIR" \
        --email "$ADMIN_EMAIL" \
        --key-type rsa2048 \
        --dns "$LEGO_DNS_PROVIDER" \
        --dns.resolvers "$LEGO_DNS_RESOLVERS" \
        --domains "$subdomain" \
        renew
done
