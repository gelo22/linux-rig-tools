import os
import sys
from pprint import pprint
import logging
import argparse
import hashlib
import time


parser = argparse.ArgumentParser(description='Nvidia GPU setup')
parser.add_argument('-c', '--config', type=str, required=True, help='For example: -c rig01.conf')
parser.add_argument('--nv-settings-path', type=str, default='nvidia-settings', help='Path to nvidia-settings')
parser.add_argument('--nv-smi-path', type=str, default='nvidia-smi', help='Path to nvidia-smi')
parser.add_argument('-i', '--config-check-interval', type=int, default=5, help='Config file check interval')
parser.add_argument('-D', '--daemon', action='store_true', default=False, help='Daemon mode')
parser.add_argument('--debug', action='store_true', default=False, help='Debug mode')
args = parser.parse_args()


def parse_conf(fp):
    gpu_list = []

    if not os.path.exists(fp):
        print('Config file \"{}\" not found'.format(fp))
        sys.exit(1)

    print('Parsing config \"{}\"'.format(fp))

    import configparser
    config = configparser.ConfigParser()
    config.read(args.config)

    for section in config:
        d = dict()
        if 'GPU' in section:
            d['gpu'] = section.replace('GPU', '').strip()
            for key in config[section]:
                d[key] = config[section][key]
            gpu_list.append(d)
    print('Parsing finished'.format(fp))
    pprint(gpu_list)
    return gpu_list


def apply_settings(lst):
    print('Applying settings...')
    cmd_list = []

    for i in lst:
        i['nv_smi'] = args.nv_smi_path
        i['nv_set'] = args.nv_settings_path
        try:
            cmd = (
                'sudo {nv_smi} -i {gpu} -pl {pl}'.format(**i),                                     # set power limit
                '{nv_set} -a \"[gpu:{gpu}]/GPUFanControlState=1\" -c :0'.format(**i),                  # gain manual fan control
                '{nv_set} -a \"[fan:{gpu}]/GPUTargetFanSpeed={fan}\" -c :0'.format(**i),               # set fan speed
                '{nv_set} -a \"[gpu:{gpu}]/GPUPowerMizerMode=1\" -c :0'.format(**i),                   # enable PowerMizer (Prefer Maximum Performance)
                '{nv_set} -a \"[gpu:{gpu}]/GPUGraphicsClockOffset[3]={core}\" -c :0'.format(**i),      # set core clok
                '{nv_set} -a \"[gpu:{gpu}]/GPUMemoryTransferRateOffset[3]={mem}\" -c :0'.format(**i),  # set memory clock
            )
            cmd_list.append(cmd)
        except KeyError:
            print('Invalid config file \"{}\". Please check key names'.format(args.config))
            sys.exit(1)

    if not args.debug: # run all commands
        os.system('sudo {} -pm ENABLED'.format(args.nv_smi_path)) # set persistent mode on all GPU
        for i in cmd_list:
            for cmd in i:
                # pprint(cmd)
                os.system(cmd)
        os.system('sudo {}'.format(args.nv_smi_path)) # get nvidia-smi status
    print('Settings applied...')


def check_md5(fp):
    md5 = hashlib.md5(open(fp, 'rb').read()).hexdigest()
    return md5


if args.daemon:
    cur_md5 = None
    prev_md5 = None

    while True:
        time.sleep(args.config_check_interval)
        cur_md5 = check_md5(args.config)

        if cur_md5 != prev_md5:
            print('Config file \"{}\" changed!'.format(args.config))
            prev_md5 = cur_md5
            conf = parse_conf(args.config)
            apply_settings(conf)
        else:
            os.system('sudo {}'.format(args.nv_smi_path)) # get nvidia-smi status
            print('Awaiting changes in \"{}\", sleeping...'.format(args.config))
else:
    conf = parse_conf(args.config)
    apply_settings(conf)
