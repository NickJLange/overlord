import subprocess
import re
import pandas as pd
# import json
# import home_network.home_network_utils
from home_network_utils import home_network_utils


class home_network(object):
    def __init__(self, name="MyCastle", data_file="macaddress.io-db.json"):
        self.hnu = home_network_utils()
        self.hnu.load_metadata(data_file)
        self.devices = None

    def updateLocalDevices(self):
        self.alive = self.updateDevicesPing()
        # FIXME - Layer in fping for remote segments
        #        self.alive = self.updateDevicesPing('192.168.3.100/24') #japan
        #        self.alive = self.updateDevicesPing('192.168.4.100/24') #WIFI
        #        self.alive = self.updateDevicesPing('192.168.20.100/24') #Wisco
        self.arp_table = self.readArpTable()
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

    def updateDevicesPing(self, cidrRange="192.168.100.0/24"):
        """
        Reads OSX fping Output - Needs to be split out for Linux
        """

        fping = subprocess.run(
            ["/usr/local/bin/fping", "-a", "-g", cidrRange], capture_output=True,
        )

        alive = dict()
        for line in fping.stdout.decode("utf-8").splitlines():
            alive[line.strip()] = 1
        return alive

    def readArpTable(self):
        """
        Reads OSX Arp Output - Needs to be split out for Linux
        """
        arp = subprocess.run(["/usr/sbin/arp", "-a"], capture_output=True,)
        scanOut = list()
        for line in arp.stdout.decode("utf-8").splitlines():
            # '? (192.168.100.9) at (incomplete) on en0 ifscope [ethernet]',
            # '? (192.168.100.10) at b8:e8:56:5:27:8e on en0 ifscope [ethernet]',
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
            scanOut.append(ds)

        myPOL = pd.DataFrame(scanOut)
        myPOL.head()
        myPOL["shortMac"] = myPOL.macAddress.apply(home_network_utils.shortenMAC)
        return myPOL
