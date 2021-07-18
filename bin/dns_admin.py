#!/usr/bin/env python3
# import pihole as ph

import requests
import hashlib
import urllib
import re
import sys


domains = {
    "dplus": [
        "disneyplus.com",
        "bamgrid.com",
        "bam.nr-data.net",
        "cdn.registerdisney.go.com",
        "cws.conviva.com",
        "d9.flashtalking.com",
        "disney-portal.my.onetrust.com",
        "disneyplus.bn5x.net",
        "js-agent.newrelic.com",
        "disney-plus.net",
        "dssott.com",
        "adobedtm.com",
    ],
    "netflix": ["netflix.com"],
    "youtube": [
        "youtube.com",
        "googlevideo.com",
        "youtu.be",
        "youtubei.googleapis.com",
        "ytimg.com",
    ],
    "playstation": ["playstation.net"],
}

token = hashlib.sha256(
    hashlib.sha256(str(sys.argv[3]).encode()).hexdigest().encode()
).hexdigest()


def add(phList, domain, comment=None, pi="localpi"):
    return cmd("add", phList, domain, comment, pi)


def sub(phList, domain, comment=None, pi="localpi"):
    return cmd("sub", phList, domain, comment, pi)


def cmd(cmd, phList, domain, comment, pi):
    url = "/admin/api.php"
    gArgs = {"list": phList, cmd: domain, "auth": token}
    pArgs = {}
    if comment:
        pArgs["comment"] = comment
    qs = urllib.parse.urlencode(gArgs)
    with requests.session() as s:
        furl = "http://" + str(pi) + url + "?" + qs
        return s.post(furl, data=pArgs).text


for dclass in domains:
    for domain in domains[dclass]:
        fdomain = re.sub(r"\.", "\\.", domain)
        fdomain = re.sub(r"^", "(\.|^)", fdomain)
        fdomain = re.sub("$", "$", fdomain)
        #            print(fdomain)
        cmd(sys.argv[2], "regex_black", fdomain, comment="Unhealthy", pi=sys.argv[1])

        # print(sub('black','pringles.com',comment="Unhealthy"))

# print(sub(''))
