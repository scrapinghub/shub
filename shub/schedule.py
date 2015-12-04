import click
from click import ClickException
from scrapinghub import Connection, APIError
from shub import scrapycfg
from shub.utils import find_api_key


@click.command(help='Schedule a spider to run on Scrapy Cloud')
@click.pass_context
@click.argument('spider', type=click.STRING)
@click.option('-p', '--project-id', help='the project ID', type=click.INT)
@click.option('-a', '--argument', help='argument for the spider (-a name=value)', multiple=True)
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
    try:
        return conn[project_id].schedule(spider, **dict(x.split('=') for x in arguments))
    except APIError as e:
        raise ClickException(e.message)


def get_project_id_from_config():
    from six.moves.configparser import NoSectionError, NoOptionError
    try:
        conf = scrapycfg.get_config()
        return conf.get('deploy', 'project')
    except (NoSectionError, NoOptionError):
        raise ClickException('missing project id')
