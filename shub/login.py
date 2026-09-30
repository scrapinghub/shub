from urllib.parse import urljoin

import click
import requests

from shub.config import GLOBAL_SCRAPINGHUB_YML_PATH, ShubConfig, load_shub_config
from shub.exceptions import AlreadyLoggedInException
from shub.utils import update_yaml_dict

HELP = """
Add your Scrapinghub API key to your global configuration file
(~/.scrapinghub.yml). This is necessary to gain access to projects associated
with your Scrapinghub account.

You can find your API key in Scrapinghub's dashboard:
https://app.zyte.com/account/apikey
"""

SHORT_HELP = "Save your Scrapinghub API key"


@click.command(help=HELP, short_help=SHORT_HELP)
def cli():
    global_conf = load_shub_config(load_local=False, load_env=False)
    if "default" in global_conf.apikeys:
        raise AlreadyLoggedInException

    conf = load_shub_config()
    key = _get_apikey(
        suggestion=conf.apikeys.get("default"),
        endpoint=global_conf.endpoints.get("default"),
    )
    with update_yaml_dict(GLOBAL_SCRAPINGHUB_YML_PATH) as conf:
        conf.setdefault("apikeys", {})
        conf["apikeys"]["default"] = key


def _get_apikey(suggestion="", endpoint=None):
    suggestion_txt = f" ({suggestion})" if suggestion else ""
    click.echo("Enter your API key from https://app.zyte.com/o/settings/apikey")
    while True:
        key = input(f"API key{suggestion_txt}: ") or suggestion
        click.echo("Validating API key...")
        if _is_valid_apikey(key, endpoint=endpoint):
            click.echo("API key is OK, you are logged in now.")
            return key
        click.echo("API key failed, try again.")


def _is_valid_apikey(key, endpoint=None):
    endpoint = endpoint or ShubConfig.DEFAULT_ENDPOINT
    validate_api_key_endpoint = urljoin(endpoint, "v2/users/me")
    r = requests.get(validate_api_key_endpoint, params={"apikey": key})  # noqa: S113
    return r.status_code == 200
