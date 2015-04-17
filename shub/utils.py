import sys, imp, os, netrc, re

SCRAPY_CFG_FILE = os.path.expanduser("~/.scrapy.cfg")
NETRC_FILE = os.path.expanduser('~/.netrc')

def missing_modules(*modules):
    """Receives a list of module names and returns those which are missing"""
    missing = []
    for module_name in modules:
        try:
            imp.find_module(module_name)
        except ImportError:
            missing.append(module_name)
    return missing

def find_api_key():
    """Finds and returns the Scrapy Cloud APIKEY"""
    key = os.getenv("SHUB_APIKEY")
    if not key:
        key = get_key_netrc()
    return key

def get_key_netrc():
    """Gets the key from the netrc file"""
    try:
        info = netrc.netrc()
    except IOError:
        return
    try:
        key, account, password = info.authenticators("scrapinghub.com") 
    except TypeError:
        return
    if key:
        return key

def is_valid_jobid(jobid):
    """Checks if a given job id is valid"""
    return bool(re.match(r'\d+/\d+/\d+$', jobid))

def is_valid_projectid(jobid):
    """Checks if a given project id is valid"""
    return bool(re.match(r'\d+$', jobid))

def is_valid_key(key):
    """Checks if a SH key is valid"""
    return bool(re.match(r'[A-Fa-f\d]{32}$', key))
