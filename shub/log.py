import datetime, click, logging
#import setuptools # not used in code but needed in runtime, don't remove!
from scrapinghub import Connection, APIError
from shub.utils import find_api_key

@click.command(help="get log records of a given job on Scrapy Cloud")
@click.option("-j", "--jobid", help="the job ID to get the log from", required=True)
@click.option("-o", "--output-file", help="the file to dump the log into", required=False)
def cli(jobid, output_file):
    key = find_api_key()
    if not key:
        print "No API key found."
        return
    connection = Connection(key)
    project_id = get_project_id(jobid)
    project = connection[project_id]
    try:
        logitems = project.job(jobid).log()
    except (APIError, AttributeError), error:
        print "Error: %s" % error.message
        return
    if output_file:
        with open(output_file, "a") as out:
            for log_item in logitems:
                line = get_line(log_item)
                out.write(line + "\n")
    else:
        for log_item in logitems:
            line = get_line(log_item)
            print line

def get_line(log_item):
    message = log_item["message"]
    level = log_item["level"]
    timestamp = log_item["time"]
    date_time = datetime.datetime.fromtimestamp(timestamp/1000)
    level_name = logging.getLevelName(level)
    line = "%s [%s] %s" % (date_time, level_name, message)
    return line

def get_project_id(job_id):
    if "/" in job_id:
        return job_id.split("/")[0]

