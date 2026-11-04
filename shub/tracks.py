from urllib.parse import quote, urljoin

import click
import requests

from shub.config import get_target_conf
from shub.exceptions import RemoteErrorException

HELP = """
List, archive and restore the deploy tracks of a Scrapy Cloud project. To
deploy to a track, use `shub deploy --track`, and to run a spider from it,
`shub schedule --track`.

By default, the tracks of your default project (as defined in scrapinghub.yml)
are used. To use another project, supply its ID or a target defined in
scrapinghub.yml, followed by a slash and the track name where there is one:

\b
    shub tracks list production
    shub tracks archive production/my-track
"""

SHORT_HELP = "Manage deploy tracks"


@click.group(help=HELP, short_help=SHORT_HELP)
def cli():
    pass


@cli.command("list", help="List the deploy tracks of a project")
@click.argument("target", required=False, default="default")
@click.option("--archived", is_flag=True, help="List only archived tracks")
def list_tracks(target, archived):
    targetconf = get_target_conf(target)
    url = _url(targetconf, "")
    params = {"archived": "true"} if archived else {}
    tracks = []
    while url:
        data = _request(targetconf, "GET", url, params=params).json()
        tracks.extend(data["results"])
        url, params = data.get("next"), None
    if not tracks:
        click.echo("No tracks found.")
        return
    width = max(len(track["name"]) for track in tracks)
    for track in tracks:
        click.echo(f"{track['name']:<{width}}  {track['version']}")


@cli.command(help="Archive a deploy track")
@click.argument("track")
def archive(track):
    targetconf, track = _resolve(track)
    _request(targetconf, "DELETE", _url(targetconf, track))
    click.echo(f"Track {track} archived.")


@cli.command(help="Restore an archived deploy track")
@click.argument("track")
def restore(track):
    targetconf, track = _resolve(track)
    _request(targetconf, "PATCH", _url(targetconf, track), json={"archived": False})
    click.echo(f"Track {track} restored.")


def _resolve(argument):
    """Return the target configuration and track name of a [TARGET/]TRACK
    argument."""
    target, _, track = argument.rpartition("/")
    return get_target_conf(target or "default"), track


def _url(targetconf, track):
    path = f"projects/{targetconf.project_id}/tracks"
    if track:
        path += f"/{quote(track)}"
    return urljoin(targetconf.endpoint, path)


def _request(targetconf, method, url, **kwargs):
    try:
        response = requests.request(
            method, url, auth=(targetconf.apikey, ""), timeout=60, **kwargs
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        try:
            detail = e.response.json()["detail"]
        except (ValueError, KeyError, TypeError):
            detail = e.response.text
        raise RemoteErrorException(
            f"{e.response.status_code} {e.response.reason}: {detail}"
        ) from e
    except requests.RequestException as e:
        raise RemoteErrorException(str(e)) from e
    return response
