#!/usr/bin/env python3


from email.mime import base
from numpy import require
import requests
import bs4
import json
import requests
import urllib3
import hashlib
from getpass import getpass
from http.cookies import SimpleCookie
import logging
#import redis
import os
import subprocess
import re
import jinja2
import datetime
from collections import defaultdict
import argparse
import json 

from dns import resolver, reversename
from dns.exception import DNSException

from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, Template

import pandas as pd
import sys

import ipaddress

##ssh- move to paramiko
from subprocess import Popen, PIPE

from pprint import pprint, pformat

# FIXME
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from home_network import home_network
from home_network_utils import home_network_utils



base_dir = os.path.join(os.path.dirname(__file__), "..")

ourNetworksFile = os.path.join(base_dir, "networks.json")
ourNetworks = json.load(open(ourNetworksFile))
print (ourNetworks)

hnu = home_network_utils()
hnu.load_metadata(data_file=os.path.join(base_dir, "macaddress.io-db.json"))


def load_meta_data():
    linez = list()
    with open(os.path.join(base_dir, "tasmota.inventory"), "r") as f:
        for line in f:
            entry_1 = line.strip().split("|")
            linez.append(entry_1)

    my_fun = pd.DataFrame(
        linez,
        columns=["macAddress", "building", "function", "location", "name", "friendly"],
    )
    #print(my_fun.head(100))
    return my_fun


def reload_network_state(universe=None):
    global ourNetworks
    home_net = home_network(
        name="HomeNet",
        data_file=os.path.join(base_dir, "macaddress.io-db.json"),
        networks=ourNetworks,building=args.building,
    )

    home_net.updateDevices()
    # Do it twice for sleepy devices/lossy wifi
    #    home_net.updateDevices()
    #    home_net.devices["macAddress"] = home_net.devices.macAddress.apply(hnu.fixMAC)
    o = home_net.devices
    o["lastSeen"] = datetime.now(timezone.utc)
    if not "firstSeen" in o.columns:
        o["firstSeen"] = o.lastSeen

    o.companyName = o.companyName.fillna(" ")
    o = pd.merge(left=universe, right=o, on="macAddress", indicator="matched")
    #    print(o.head(30))
    return o


def generate_ansible_inventory(network_data=None,universe=None):
    # load our device data AGAIN
    global base_dir
    global args
    inventory = defaultdict(dict)
    rooms = defaultdict(list)
    kinds = defaultdict(list)
    buildings = defaultdict(list)
    filename = os.path.join(base_dir, "tasmota.inventory")
    with open(filename, "r") as f:
        for line in f:
            ### FIXME - Add type support
            (mac, building, kind, room, device, friendly) = line.strip().split("|")
            rooms[room].append("%s_%s" % (room, device))
            kinds[kind].append("%s_%s" % (room, device))
            buildings[building].append("%s_%s" % (room, device))
            inventory[mac] = {
                "building": building,
                "kind": kind,
                "room": room,
                "name": device,
                "friendly": friendly,
            }
    # generate inventory
    for mac in inventory:
        x = network_data.loc[network_data.macAddress == mac, "ipAddress"]
        if not x.empty:
            inventory[mac]["ipAddress"] = x.values[0]
        else:
#            print(mac)
            t = universe.loc[(universe.macAddress == mac),["macAddress","building", "location", "name"]]
            print(t.values[0]) if (inventory[mac]["building"] == args.building) else None
    # jinja2.Template()
    file_loader = FileSystemLoader(os.path.join(base_dir, "templates"))
    env = Environment(loader=file_loader)

    tastm = env.get_template(os.path.join("tasmota.tmpl.j2"))
    ou = tastm.render(
        inventory=inventory, rooms=rooms, buildings=buildings, kinds=kinds
    )
    parsedTemplates = os.path.join(base_dir, "ansible", "hosts")
    with open(parsedTemplates, "w") as f:
        f.write(ou)
    # generate per-device config - just friendly name?
    for mac in inventory.keys():
        tasmota_name = "%s_%s" % (inventory[mac]["room"], inventory[mac]["name"])
        hostvars_template = env.get_template("tasmota.hostvars.j2")
        friendly_name = None
        if inventory[mac]["friendly"]:
            friendly_name = inventory[mac]["friendly"]
        ou = hostvars_template.render(
            tasmota_name=tasmota_name, friendly_name=friendly_name
        )
        filename = os.path.join(base_dir, "ansible", "host_vars", tasmota_name)
        with open(filename, "w") as f:
            f.write(ou)

parser =  argparse.ArgumentParser()
parser.add_argument(
    "--building",
    action="store",
    dest="building",
    required=True,
    help="Print lots of debugging statements",
)
args = parser.parse_args()

universe = load_meta_data()
network_data = reload_network_state(universe)
# debug
temp = network_data.loc[
    #        (network_data.companyName.str.contains("Espressif Inc"))
    (network_data.matched == "both")
    & (network_data.building == args.building),
    # & (network_data.pingable),
    ["ipAddress", "companyName", "building", "location", "name", "function", "pingable"],
].sort_values(by=["building", "location", "name"])

print(f"Discovery Results {temp.count()[0]}/{universe.count()[0]}")
print(temp)
generate_ansible_inventory(network_data,universe)
