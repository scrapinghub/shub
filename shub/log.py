import click, requests
from shub.utils import find_api_key, get_config

@click.command(help="get log records of a given job on Scrapy Cloud")
@click.argument("jobid")
@click.option("-t", "--output-format", help="the log format to be outputed", required=False, type=click.Choice(["jl", "json", "text", "csv"]), default="text")
@click.option("-o", "--output-file", help="the file to dump the log into", required=False)
def cli(jobid, output_file, output_format):
    config = get_config()
    try:
        key = config["auth"]["key"]
    except (TypeError, KeyError):
        key = find_api_key()
        if not key:
            print "No API key found. Quitting..."
            return
    url = "https://storage.scrapinghub.com/logs/%s" % jobid
    headers = _create_headers(output_format=output_format)
    log = requests.get(url, headers=headers, auth=(key, "")).text
    if output_file:
        with open(output_file, "a") as out:
            out.write(log)
    else:
        print log

def _create_headers(**kargs):
    headers = dict()
    output_format = kargs["output_format"]
    map_formats = {
        "jl": "application/x-jsonlines",
        "json": "application/json",
        "text": "text/plain",
        "csv": "text/csv",
    }
    if output_format:
        headers["Accept"] = map_formats[output_format]
    return headers
