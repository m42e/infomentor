import configparser
import os

_config = None


def _set_defaults(config):
    config.add_section('pushover')
    config.add_section('general')
    config.add_section('smtp')
    config['pushover']['apikey'] = ''
    config['general']['secretkey'] = ''
    config['general']['baseurl'] = ''
    config['general']['adminmail'] = ''
    config['general']['im1url'] = 'https://im1.infomentor.de/Germany/Germany/Production'
    config['general']['mimurl'] = 'https://mein.infomentor.de'
    config['smtp']['server'] = ''
    config['smtp']['username'] = ''
    config['smtp']['password'] = ''

def load(cfg_file='informentor.ini'):
    '''Load the config from the file'''
    global _config
    if _config is None:
        _config = configparser.ConfigParser()
        if not os.path.isfile(cfg_file):
            _set_defaults(_config)
            save(cfg_file)
        _config.read(cfg_file)
    return _config

def save(cfg_file='informentor.ini'):
    '''Write config to file'''
    global _config
    with open(cfg_file, 'w+') as f:
        _config.write(f)
