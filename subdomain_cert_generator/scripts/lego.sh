#!/bin/bash

ADMIN=dns@wafuu.design

mkdir -p ../lego-data/

for subdomain in newyork.nicklange.family wisconsin.nicklange.family miyagi.nicklange.family tele.newyork.nicklange.family; 
 do  
  echo "Renewing Certs for $subdomain"
  podman run -v ../lego-data/:/.lego/ --env-file ../etc/lego_secrets.env -it goacme/lego --email $ADMIN --dns porkbun --domains '*.'$subdomain --domains $subdomain run
done