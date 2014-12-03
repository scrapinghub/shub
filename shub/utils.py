import sys, imp, os, netrc

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

def fatal(message):
    """Print a message to stderr and exit with error code 1"""
    if not message.endswith('\n'):
        message += '\n'
    sys.stderr.write(message)
    sys.exit(1)
