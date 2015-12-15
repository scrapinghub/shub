import click
from click import ClickException
from scrapinghub import Connection, APIError
from shub.config import load_shub_config


@click.command(help='Schedule a spider to run on Scrapy Cloud')
@click.argument('spider', type=click.STRING)
@click.option('-p', '--project-id', help='the project ID', type=click.INT)
@click.option('-a', '--argument', help='argument for the spider (-a name=value)', multiple=True)
def cli(project_id, spider, argument):
    conf = load_shub_config()
    project_id = project_id or conf.get_project_id('default')
    apikey = conf.get_apikey(project_id or 'default')
    job_key = schedule_spider(apikey, project_id, spider, argument)
    click.echo(
        'Spider {} scheduled, watch it running here:\n'
        'https://dash.scrapinghub.com/p/{}/job/{}/{}'.format(spider, *job_key.split('/'))
    )


def schedule_spider(apikey, project_id, spider, arguments=()):
    conn = Connection(apikey)
    try:
        return conn[project_id].schedule(spider, **dict(x.split('=') for x in arguments))
    except APIError as e:
        raise ClickException(e.message)
