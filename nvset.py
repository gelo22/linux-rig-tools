from collections import OrderedDict
import json
import os
import sys
from pprint import pprint
import logging
import argparse
import hashlib
import time
import logging as log
import subprocess


if sys.version_info[0] < 3:
    print('Please use Python 3\nExample: python3 {}'.format(sys.argv[0]))
    sys.exit(1)


import configparser


parser = argparse.ArgumentParser(description='Nvidia GPU setup')
parser.add_argument('-c', '--config', type=str, required=True, help='For example: -c rig01.conf')
parser.add_argument('--start-delay', type=int, default=15, help='Add delay if first run')
parser.add_argument('-M', '--make-config', action='store_true', default=False, help='Make config template')
parser.add_argument('--nv-set-path', type=str, default='nvidia-settings', help='Path to nvidia-settings')
parser.add_argument('--nv-smi-path', type=str, default='nvidia-smi', help='Path to nvidia-smi')
parser.add_argument('--nv-set-env', type=str, nargs='+', default=['DISPLAY=\":0\"', 'XAUTHORITY=\"/var/run/lightdm/root/:0\"'], help='nvidia-settings extra environment variables')
parser.add_argument('--api-url', type=str, default='http://localhost:8000/api/v1', help='API url')
parser.add_argument('--api-timeout', type=int, default=10, help='API read timeout')

# overclock default values
parser.add_argument('--pl', type=int, default=80, help='Default power limit')
parser.add_argument('--core', type=int, default=0, help='Default core clock')
parser.add_argument('--mem', type=int, default=0, help='Default memory clock')
parser.add_argument('--fan', type=int, default=60, help='Default FAN speed')
parser.add_argument('--fan-auto', action='store_true', default=False, help='Enable FAN auto mode')
parser.add_argument('--max-temp', type=int, default=70)

parser.add_argument('-i', '--config-check-interval', type=int, default=5, help='Config file check interval')
parser.add_argument('-D', '--daemon', action='store_true', default=False, help='Daemon mode')
parser.add_argument('--debug', action='store_true', default=False, help='Debug mode')
args = parser.parse_args()


if args.debug:
    DEBUG = True
    LOG_LEVEL = log.DEBUG
else:
    DEBUG = False
    LOG_LEVEL = log.INFO

log.basicConfig(format='[%(levelname)s] %(message)s', level=LOG_LEVEL)

FIRST_RUN = True


def check_config_file(fp):
    if not os.path.exists(fp):
        log.error('Config file \"{}\" not found'.format(fp))
        sys.exit(1)


def parse_conf(fp=args.config):
    config = configparser.ConfigParser(dict_type=OrderedDict)
    config.read(fp)

    gpu_list = []

    check_config_file(fp)

    print('Parsing config \"{}\"'.format(fp))

    for section in config:
        d = dict()
        for key in config[section]:
            d[key] = config[section][key]
        if d:
            gpu_list.append(d)
    log.info('Parsing finished'.format(fp))
    pprint(gpu_list)
    return gpu_list


def read_api(url=args.api_url, debug=args.debug, api_timeout=args.api_timeout):
    import urllib.request
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlparse
    from socket import timeout

    log.info('Reading API ...')

    try:
        resp = urllib.request.urlopen(url, timeout=api_timeout).read().decode('utf-8')
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
    config = configparser.ConfigParser(dict_type=OrderedDict)
    config.read(fp)

    d = read_api()
    if not d:
        log.error('API data is empty')
        return False

    api_data = d[0]['cards']

    for i in api_data:
        key = i.get('bus_id')

        card_conf = dict(
            pl=args.pl,
            core=args.core,
            mem=args.mem,
            fan=args.fan,
            uuid=i.get('uuid'),
            index=i.get('index'),
        )

        config[key] = card_conf

    with open(fp, 'w') as configfile:
        log.info('Writing config file \"{}\" ...'.format(fp))
        config.write(configfile)


def set_fan():
    d = read_api()
    if not d:
        log.error('API data is empty')
        return False

    api_data = d[0]['cards']

    cmd_list = []
    for i in api_data:
        i['nv_set'] = args.nv_set_path
        i['env'] = ' '.join(args.nv_set_env)

        cur_temp = i.get('temp')
        cur_fan = i.get('fan')
        temp_delta = abs(cur_temp - (cur_fan - 20))

        new_fan = cur_temp + 20
        fan_delta = abs(new_fan - cur_fan)

        if temp_delta > 2 and cur_temp < args.max_temp:
            i['new_fan'] = new_fan

        if cur_temp >= args.max_temp or new_fan > 100:
            new_fan = 100
            i['new_fan'] = new_fan

        print(fan_delta, cur_temp >= args.max_temp, new_fan, cur_fan)
        if all([fan_delta > 5, cur_temp >= args.max_temp, 100 > new_fan > cur_fan]):
            cmd = '{env} sudo {nv_set} -a \"[fan:{index}]/GPUTargetFanSpeed={new_fan}\"'.format(**i)
            cmd_list.append(cmd)

    run_proc(cmd_list)


def apply_settings(lst):
    if FIRST_RUN:
        log.info('First run, waiting {} seconds ...'.format(args.start_delay))
        time.sleep(args.start_delay)
        FIRST_RUN = False

    log.info('Applying settings...')
    if not args.debug:
        os.system('sudo {} -pm ENABLED'.format(args.nv_smi_path)) # set persistent mode on all GPU

    for i in lst:
        i['nv_smi'] = args.nv_smi_path
        i['nv_set'] = args.nv_set_path
        if args.nv_set_env:
            i['env'] = ' '.join(args.nv_set_env)

        nv_attr = [
            '{env} sudo {nv_set}',
            '-a \"[gpu:{index}]/GPUFanControlState=1\"',                   # gain manual fan control
            '-a \"[fan:{index}]/GPUTargetFanSpeed={fan}\"',                # set fan speed
            '-a \"[gpu:{index}]/GPUPowerMizerMode=1\"',                    # enable PowerMizer (Prefer Maximum Performance)
            '-a \"[gpu:{index}]/GPUGraphicsClockOffset[2]={core}\"',       # set core clock
            '-a \"[gpu:{index}]/GPUMemoryTransferRateOffset[2]={mem}\"',   # set memory clock
            '-c :0',
        ]

        if args.fan_auto:
            nv_attr = nv_attr[0:1] + nv_attr[3:]

        try:
            cmd = (
                'sudo {nv_smi} -i {index} -pl {pl}'.format(**i),           # set power limit
                ' '.join(nv_attr).format(**i),
            )
            log.debug('; '.join(cmd))

            run_proc(cmd)
        except KeyError:
            log.error('Invalid config file \"{}\". Please check key names'.format(args.config))
            sys.exit(1)
    log.info('Settings applied...')


def run_proc(cmd_list, fake=False):
    if fake:
        return

    for cmd in cmd_list:
        out, err = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()
        log.info(cmd)
        if out:
            log.warning(out.decode('utf-8').strip())
        if err:
            log.error(err.decode('utf-8').strip())


def check_md5(fp):
    check_config_file(fp)
    md5 = hashlib.md5(open(fp, 'rb').read()).hexdigest()
    log.debug('{} {}'.format(fp, md5))
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
        cur_md5 = check_md5(args.config)

        if args.fan_auto:
            set_fan()

        if cur_md5 != prev_md5:
            log.warning('Config file \"{}\" changed!'.format(args.config))
            prev_md5 = cur_md5

            parse_or_genconf()
        else:
            log.info('Awaiting changes in \"{}\", sleeping...'.format(args.config))

        time.sleep(args.config_check_interval)
else:
    parse_or_genconf()
