import imp, os, netrc, ConfigParser

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
    key = os.getenv("SH_APIKEY")
    if not key:
        key = get_key_netrc()
    if not key:
        key = get_key_scrapy()
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

def get_key_scrapy():
    """Gets the key from the scrapy config file"""
    if os.path.isfile(SCRAPY_CFG_FILE):
        reader = ConfigParser.ConfigParser()
        reader.read(SCRAPY_CFG_FILE)
        try:
            key = reader.get('deploy', 'username')
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            key = ''
        return key
