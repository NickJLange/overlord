import json
import pandas as pd


class home_network_utils(object):
    def __init__(self):
        self.idf = None
        return

    def load_metadata(self, data_file=None):
        if not data_file:
            return
        deets = list()
        with open(data_file, "r") as jraw:
            for line in jraw:
                q = json.loads(line)
                deets.append(q)
        idf = pd.DataFrame(deets)
        idf["lmac"] = idf.oui.str.lower()
        self.idf = idf

    @staticmethod
    def fixMAC(inMAC):
        """
        Shortens MAC and adds matching zero
        returns none on bad data
        """
        working = inMAC.split(":")
        if len(working) != 6:
            return None
        output = list()

        for ind in range(0, 6):
            outputVal = working[ind].lower()
            if len(outputVal) == 1:  # MAC Abbreviation
                outputVal = "0%s" % outputVal
            output.append(outputVal)
        return ":".join(output)

    @staticmethod
    def shortenMAC(inMAC):
        """
        Shortens MAC and adds matching zero
        returns none on bad data
        """
        if not inMAC:
            return None
        if ":" not in inMAC:
            return None
        working = inMAC.split(":")
        if len(working) != 6:
            return None
        output = list()

        for ind in range(0, 3):
            outputVal = working[ind].lower()
            if len(outputVal) == 1:  # MAC Abbreviation
                outputVal = "0%s" % outputVal
            output.append(outputVal)
        return ":".join(output)
