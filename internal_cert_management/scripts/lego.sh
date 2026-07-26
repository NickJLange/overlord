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

lego_cmd() {
    local key_type="$1"; shift
    local cert_file="$LEGO_DATA_DIR/certificates/$1.crt"
    local action="renew"
    if [ ! -f "$cert_file" ]; then
        echo "No existing cert found, running initial issuance"
        action="run"
    fi
    lego \
        --path "$LEGO_DATA_DIR" \
        --email "$ADMIN_EMAIL" \
        --key-type "$key_type" \
        --dns "$LEGO_DNS_PROVIDER" \
        --dns.resolvers "$LEGO_DNS_RESOLVERS" \
        "$@" \
        "$action"
}

for subdomain in "${subdomains_ec256[@]}"; do
    echo "Processing ec256 cert for $subdomain"
    lego_cmd ec256 "_.$subdomain" --domains "*.$subdomain" --domains "$subdomain"
done

for subdomain in "${subdomains_rsa2048[@]}"; do
    echo "Processing rsa2048 cert for $subdomain"
    lego_cmd rsa2048 "$subdomain" --domains "$subdomain"
done
