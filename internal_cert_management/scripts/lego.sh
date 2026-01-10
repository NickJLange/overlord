#!/bin/bash

set -e

# Load configuration from .env file
if [ -f "$(dirname "$0")/../.env" ]; then
    source "$(dirname "$0")/../.env"
else
    echo "Error: .env file not found. Please copy .env.example to .env and configure."
    exit 1
fi

# Validate required variables
: "${ADMIN_EMAIL:?ADMIN_EMAIL is not set}"
: "${SUBDOMAINS_EC256:?SUBDOMAINS_EC256 is not set}"
: "${SUBDOMAINS_RSA2048:?SUBDOMAINS_RSA2048 is not set}"

# Convert space-separated strings to arrays
read -ra subdomains_ec256 <<< "$SUBDOMAINS_EC256"
read -ra subdomains_rsa2048 <<< "$SUBDOMAINS_RSA2048"

for type in ec256
do
    for subdomain in ${subdomains_ec256[@]}
    do
        mkdir -p "../lego-data/$subdomain/$type/"
        echo "Renewing Certs for $subdomain/$type"
        ls -ld ../lego-data/$subdomain/$type/ ../lego-data/

        podman run -v ./lego-data/:/.lego/ \
        -v ./lego-data/$subdomain/$type/:/.lego/certificates/ \
        --env-file ./etc/lego_secrets.env \
        --read-only \
        -it goacme/lego \
        --email "$ADMIN_EMAIL" \
        --key-type=$type \
        --dns "$LEGO_DNS_PROVIDER" \
        --dns.resolvers "$LEGO_DNS_RESOLVERS" \
        --domains '*.'$subdomain --domains $subdomain \
        renew
    done
done

for type in rsa2048
do
    for subdomain in ${subdomains_rsa2048[@]}
    do
        mkdir -p "../lego-data/$subdomain/$type/"
        echo "Renewing Certs for $subdomain/$type"
        ls -ld ../lego-data/$subdomain/$type/ ../lego-data/

        podman run -v ./lego-data/:/.lego/ \
        -v ./lego-data/$subdomain/$type/:/.lego/certificates/ \
        --env-file ./etc/lego_secrets.env \
        --read-only \
        -it goacme/lego \
        --email "$ADMIN_EMAIL" \
        --key-type=$type \
        --dns "$LEGO_DNS_PROVIDER" \
        --dns.resolvers "$LEGO_DNS_RESOLVERS" \
        --domains $subdomain \
        renew
    done
done
