from ConfigParser import NoSectionError, NoOptionError
import click
from click import ClickException
from hubstorage import HubstorageClient
from shub import scrapycfg
from shub.utils import find_api_key


@click.command(help='Schedule a spider to run on Scrapy Cloud')
@click.pass_context
@click.argument("spider", type=click.STRING)
@click.option("-p", "--project-id", help="the project ID", type=click.INT)
@click.option("-a", "--argument", help="argument for the spider", multiple=True)
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
    hc = HubstorageClient(auth=apikey)
    project = hc.get_project(project_id)
    if project.ids.spider(spider) is None:
        raise ClickException(
            'Spider \'{}\' doesn\'t exist in project {}'.format(
                spider, project_id
            )
        )
    job = hc.push_job(projectid=project_id, spidername=spider,
                      spider_args=dict(x.split('=') for x in arguments))
    return job.key


def get_project_id_from_config():
    try:
        conf = scrapycfg.get_config()
        return conf.get('deploy', 'project')
    except (NoSectionError, NoOptionError):
        raise ClickException('missing project id')
