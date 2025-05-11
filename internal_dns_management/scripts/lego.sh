#!/bin/bash

ADMIN=dns@wafuu.design

types=(rsa2048 ec256)
#types=(rsa2048)

subdomains=(newyork.nicklange.family wisconsin.nicklange.family miyagi.nicklange.family)
#subdomains=(newyork.nicklange.family)

#for type in "ec256" "rsa2048"
#for type in "ec256" "rsa2048"
for type in ${types[@]}
do
    for subdomain in ${subdomains[@]}
#    for subdomain in newyork.nicklange.family wisconsin.nicklange.family miyagi.nicklange.family tele.newyork.nicklange.family;
    do
        mkdir -p "../lego-data/$subdomain/$type/"
        echo "Renewing Certs for $subdomain/$type"
        ls -ld ../lego-data/$subdomain/$type/ ../lego-data/

        podman run -v ./lego-data/:/.lego/ \
        -v ./lego-data/$subdomain/$type/:/.lego/certificates/ \
        --env-file ./etc/lego_secrets.env \
        --read-only \
        -it goacme/lego \
        --email $ADMIN \
        --key-type=$type \
        --dns porkbun \
        --dns.resolvers 9.9.9.9:53 \
        --domains '*.'$subdomain --domains $subdomain \
        renew
    done
done
