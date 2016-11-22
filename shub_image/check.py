import click
import requests

from shub_image.utils import load_status_url

SHORT_HELP = "Check a deploy task's status url saved in a temporary file."

HELP = """
A command to check your release task state for asynchronous deploy mode.
Does a simple GET request to Dash with an URL which it reads from a
temporary file.
"""


@click.command(help=HELP, short_help=SHORT_HELP)
@click.option("--id", type=int, help="status id to check deploy results")
def cli(id):
    status_url = load_status_url(id)
    status_req = requests.get(status_url, timeout=300)
    status_req.raise_for_status()
    result = status_req.json()
    click.echo("Deploy results: {}".format(result))
