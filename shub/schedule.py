from ConfigParser import NoSectionError, NoOptionError
import click
from click import ClickException
from scrapinghub import Connection
from shub import scrapycfg
from shub.utils import find_api_key


@click.command(help='Schedule a spider to run on Scrapy Cloud')
@click.pass_context
@click.argument("spider", type=click.STRING)
@click.option("-p", "--project-id", help="the project ID", type=click.INT)
@click.option("-a", "--argument", help="argument for the spider (-a name=value)", multiple=True)
def cli(context, project_id, spider, argument):
    apikey = find_api_key()
    if not apikey:
        raise ClickException('Scrapinghub API key not found: please, run \'scrapy login\' first')
    project_id = project_id or get_project_id_from_config()
    job_key = schedule_spider(apikey, project_id, spider, argument)
    click.echo(
        'Spider {} scheduled: {}\nCheck the spider execution at: '
        'https://dash.scrapinghub.com/p/{}/job/{}/{}'.format(spider, job_key, *job_key.split('/'))
    )


def schedule_spider(apikey, project_id, spider, arguments=()):
    conn = Connection(apikey)
    if project_id not in conn.project_ids():
        raise ClickException("project {} doesn\'t exist".format(project_id))
    project = conn[project_id]
    if spider not in [sp['id'] for sp in project.spiders()]:
        raise ClickException("spider {} doesn\'t exist in project {}".format(spider, project.id))
    return project.schedule(spider, **dict(x.split('=') for x in arguments))


def get_project_id_from_config():
    try:
        conf = scrapycfg.get_config()
        return conf.get('deploy', 'project')
    except (NoSectionError, NoOptionError):
        raise ClickException('missing project id')
