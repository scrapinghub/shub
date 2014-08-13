import imp, os, json, ConfigParser

def missing_modules(*modules):
    """Receives a list of module names and returns those which are missing"""
    missing = []
    for module_name in modules:
        try:
            imp.find_module(module_name)
        except ImportError:
            missing.append(module_name)
    return missing

def get_config():
    """Returns a dict representing the configuration file's content"""
    home_cfg = os.path.expanduser("~/.shub.cfg")
    if os.path.isfile(home_cfg):
        with open(home_cfg, 'r') as config_file:
            try:
                file_content = json.loads(config_file.read())
            except ValueError:
                file_content = None
            return file_content

def find_api_key():
    """Finds and returns the Scrapy Cloud APIKEY"""
    key = os.getenv("SH_APIKEY")
    if key:
        return key
    reader = ConfigParser.ConfigParser()
    home_cfg = os.path.expanduser("~/.scrapy.cfg")
    local_cfg = os.path.expanduser("scrapy.cfg")
    if os.path.isfile(local_cfg):
        reader.read(local_cfg)
    elif os.path.isfile(home_cfg):
        reader.read(home_cfg)
    else:
        return
    try:
        key = reader.get("deploy", "username")
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError()):
        key = ""
    return key
