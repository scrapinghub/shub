import sys

import click
import lxml.html
import requests


def get_status(url):
    r = requests.get(url)
    doc = lxml.html.fromstring(r.text)
    try:
        return doc.xpath('.//div[@id="lastChecked"]//div[@id="statusIcon"]')[0].get("class").upper()
    except:
        return "UNKNOWN"

status_pages = (
    ("API", "http://status.scrapinghub.com/1060348"),
    ("Crawlera", "http://status.scrapinghub.com/526504"),
    ("Dash", "http://status.scrapinghub.com/572454"),
)

@click.command(help="Display current Scrapinghub API status")
def cli():
    exitcode = 0
    for service, url in status_pages:
        print "%(service)-10s: %(status)8s" % {"service": service,
                                               "status": get_status(url)}
    sys.exit(exitcode)

