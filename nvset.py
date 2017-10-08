import json
import os
import sys
from pprint import pprint
import logging
import argparse
import hashlib
import time
import logging as log


if sys.version_info[0] < 3:
    print('Please use Python 3\nExample: python3 {}'.format(sys.argv[0]))
    sys.exit(1)


parser = argparse.ArgumentParser(description='Nvidia GPU setup')
parser.add_argument('-c', '--config', type=str, required=True, help='For example: -c rig01.conf')
parser.add_argument('-C', '--make-config', action='store_true', default=False, help='Daemon mode')
parser.add_argument('--nv-settings-path', type=str, default='nvidia-settings', help='Path to nvidia-settings')
parser.add_argument('--nv-smi-path', type=str, default='nvidia-smi', help='Path to nvidia-smi')
parser.add_argument('--api-url', type=str, default='http://localhost:8000/api/v1', help='API url')
parser.add_argument('-i', '--config-check-interval', type=int, default=5, help='Config file check interval')
parser.add_argument('-D', '--daemon', action='store_true', default=False, help='Daemon mode')
parser.add_argument('--debug', action='store_true', default=False, help='Debug mode')
args = parser.parse_args()


import configparser
config = configparser.ConfigParser()
config.read(args.config)


if args.debug:
    DEBUG = True
    LOG_LEVEL = log.DEBUG
else:
    DEBUG = False
    LOG_LEVEL = log.INFO

log.basicConfig(format='[%(levelname)s] %(message)s', level=LOG_LEVEL)


def parse_conf(fp=args.config):
    gpu_list = []

    if not os.path.exists(fp):
        print('Config file \"{}\" not found'.format(fp))
        sys.exit(1)

    print('Parsing config \"{}\"'.format(fp))

    for section in config:
        d = dict()
        for key in config[section]:
            d[key] = config[section][key]
        if d:
            gpu_list.append(d)
    print('Parsing finished'.format(fp))
    pprint(gpu_list)
    return gpu_list


def read_api(url=args.api_url, debug=args.debug):
    import urllib.request
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlparse
    from socket import timeout

    try:
        resp = urllib.request.urlopen(url, timeout=2).read()
    except (HTTPError, URLError) as error:
        log.error('Data is not retrieved. Error: {}\nURL: {}\n'.format(error, url))
    except timeout:
        log.error('Time out. URL: {}\n'.format(url))
    else:
        j = json.loads(resp)
        if debug:
            pprint(j)
        return(j)


def gen_conf(fp=args.config):
    def_conf = dict(
        pl=100,
        core=0,
        mem=0,
        fan=60
    )

    d = read_api()
    if not d:
        log.error('API data is empty')
        return False

    api_data = d[0]['cards']


    for i in api_data:
        key = i.get('bus_id')

        def_conf.update(
            dict(
                uuid=i.get('uuid'),
                index=i.get('index'),
            )
        )

        config[key] = def_conf

    with open(fp, 'w') as configfile:
        log.info('Writing config file \"{}\" ...'.format(fp))
        config.write(configfile)


def apply_settings(lst):
    print('Applying settings...')
    cmd_list = []

    for i in lst:
        i['nv_smi'] = args.nv_smi_path
        i['nv_set'] = args.nv_settings_path
        try:
            cmd = (
                'sudo {nv_smi} -i {index} -pl {pl}'.format(**i),                                         # set power limit
                '{nv_set} -a \"[gpu:{index}]/GPUFanControlState=1\" -c :0'.format(**i),                  # gain manual fan control
                '{nv_set} -a \"[fan:{index}]/GPUTargetFanSpeed={fan}\" -c :0'.format(**i),               # set fan speed
                '{nv_set} -a \"[gpu:{index}]/GPUPowerMizerMode=1\" -c :0'.format(**i),                   # enable PowerMizer (Prefer Maximum Performance)
                '{nv_set} -a \"[gpu:{index}]/GPUGraphicsClockOffset[3]={core}\" -c :0'.format(**i),      # set core clok
                '{nv_set} -a \"[gpu:{index}]/GPUMemoryTransferRateOffset[3]={mem}\" -c :0'.format(**i),  # set memory clock
            )
            log.debug(' '.join(cmd))
            cmd_list.append(cmd)
        except KeyError:
            print('Invalid config file \"{}\". Please check key names'.format(args.config))
            sys.exit(1)

    if not args.debug: # run all commands
        os.system('sudo {} -pm ENABLED'.format(args.nv_smi_path)) # set persistent mode on all GPU
        for i in cmd_list:
            for cmd in i:
                os.system(cmd)
        os.system('sudo {}'.format(args.nv_smi_path)) # get nvidia-smi status
    print('Settings applied...')


def check_md5(fp):
    md5 = hashlib.md5(open(fp, 'rb').read()).hexdigest()
    return md5


def parse_or_genconf():
    if args.make_config:
        gen_conf()
    else:
        conf = parse_conf()
        apply_settings(conf)


if args.daemon:
    cur_md5 = None
    prev_md5 = None

    while True:
        time.sleep(args.config_check_interval)
        cur_md5 = check_md5(args.config)

        if cur_md5 != prev_md5:
            print('Config file \"{}\" changed!'.format(args.config))
            prev_md5 = cur_md5
            parse_or_genconf()
        else:
            if not args.debug:
                os.system('sudo {}'.format(args.nv_smi_path)) # get nvidia-smi status
            print('Awaiting changes in \"{}\", sleeping...'.format(args.config))
else:
    parse_or_genconf()
