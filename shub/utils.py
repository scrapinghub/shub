import imp
import os
import ConfigParser

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
        key = reader.get('deploy', 'username')
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError()):
        key = ""
    return key
