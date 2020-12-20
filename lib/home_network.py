import subprocess
import re
import pandas as pd
from pprint import pprint

# import json
# import home_network.home_network_utils
from home_network_utils import home_network_utils


class home_network(object):
    def __init__(
        self, name="MyNetwork", data_file="macaddress.io-db.json", networks=None
    ):
        self.hnu = home_network_utils()
        self.hnu.load_metadata(data_file)
        self.devices = None
        self.alive = dict()
        self.raw_arp = dict()
        self.networks = networks

    def updateDevices(self):
        for network in self.networks:
            pprint(network)
            self.updateDevicesPing(network)
            self.updateArpTable(network)

        scanOut = list()
        for m, ds in self.raw_arp.items():
            scanOut.append(ds)
        myPOL = pd.DataFrame(scanOut)
        myPOL.head()
        myPOL["shortMac"] = myPOL.macAddress.apply(home_network_utils.shortenMAC)
        self.arp_table = myPOL

        o = self.arp_table.merge(
            how="left",
            right=self.hnu.idf,
            left_on="shortMac",
            right_on="lmac",
            indicator="found",
        )
        o.head()

        self.devices = o
        return

    def updateDevicesPing(self, network=None):
        """
        Reads OSX fping Output - Needs to be split out for Linux
        """
        if not network:
            return
        ssh_cmd = [
            "/usr/local/bin/fping",
            "-a",
            "-g",
            network["cidrRange"],
        ]
        if "jumphost" in network:
            ssh_cmd.insert(0, "%s" % network["jumphost"])
            ssh_cmd.insert(0, "/usr/bin/ssh")
        fping = subprocess.run(ssh_cmd, capture_output=True,)

        for line in fping.stdout.decode("utf-8").splitlines():
            self.alive[line.strip()] = 1
        return self.alive

    def updateArpTable(self, network=None):
        """
        Reads OSX Arp Output - Needs to be split out for Linux
        """
        arp_cmd = ["/usr/sbin/arp", "-n", "-a"]
        if "jumphost" in network:
            arp_cmd.insert(0, "%s" % network["jumphost"])
            arp_cmd.insert(0, "/usr/bin/ssh")
        arp = subprocess.run(arp_cmd, capture_output=True,)

        for line in arp.stdout.decode("utf-8").splitlines():
            # '? (192.168.100.900) at (incomplete) on en0 ifscope [ethernet]',
            # '? (192.168.100.100) at xx:xx:xx:xx:xx:xx on en0 ifscope [ethernet]',
            if "incomplete" in line:
                continue
            output = line.split(" ")
            isAlive = False
            found = re.match(r"\((\d+\.\d+\.\d+\.\d+)\)", output[1].strip())
            if not found:
                continue
            ip = found.group(1)
            if ip in self.alive:
                isAlive = True
            #    print ("%s"%output)
            ds = {
                "macAddress": output[3],
                "ifAddress": output[5],
                "ipAddress": ip,
                "pingable": isAlive,
                # VLA - fix me later
                #        'media':output[6],
            }
            self.raw_arp[output[3]] = ds
