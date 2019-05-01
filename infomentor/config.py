import configparser
import os

_config = None

def load():
    global _config
    if _config is None:
        _config = configparser.ConfigParser()
        if not os.path.isfile('infomentor.ini'):
            _config.add_section('pushover')
            _config.add_section('general')
            _config.add_section('smtp')
            _config['pushover']['apikey'] = ''
            _config['general']['secretkey'] = ''
            _config['smtp']['server'] = ''
            _config['smtp']['username'] = ''
            _config['smtp']['password'] = ''
            with open('infomentor.ini', 'w+') as f:
                _config.write(f)
        _config.read('infomentor.ini')
    return _config


