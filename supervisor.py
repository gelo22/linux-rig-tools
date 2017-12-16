#!/usr/bin/env python3

import os
import time
import sys
from subprocess import Popen, PIPE
import traceback
import argparse
import configparser
import shlex

# Example start:
# python3 supervisor.py --config=config.ini
# or:
# ./supervisor.py --config=config.ini

# parse args
parser = argparse.ArgumentParser()
parser.add_argument('--config', help='config file location')
parser.add_argument('--supervisor_pid_file', default='/tmp/supervisor.pid', help='Pid file for supervisor daemon')
parser.add_argument('--miner_name', default='ccminer', help='miner name which will be installed')
parser.add_argument('--watchdog_options', default='', help='Options for watchdog')
parser.add_argument('--api_options', default='--api --gpu-type nvidia --getdata-interval 10', help='Options for api')
parser.add_argument('--oc_options', default='-c oc.ini -D', help='Options for oc')
args = parser.parse_args()

miner_options = {'ccminer': {'options': {'pool': '',
                                         'user': '',
                                         'password': ''
                                        },
                             'template': '-o {pool} -u {user} -p {password} {extra_options}'
                            },
                 'ethminer': {'options': {'pool': '',
                                          'user': '',
                                          'password': '',
                                          'worker_name': ''
                                         },
                             'template': '-S {pool} -O {user}.{worker_name}:{password} {extra_options}'
                             }
                }

def parse_configuration(args):
    '''Parse configuration from config and cmd'''
    # go to root dir
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)
    # get config from file
    if not os.path.isfile(args.config):
        print('Config is not exist, generating default config')
        _gen_conf(args.config, args.miner_name)
    conf = configparser.ConfigParser()
    conf.read(args.config)
    for opt in conf['miner']:
        if opt == 'name':
            continue
        if conf['miner'][opt] == 'change_me':
            print('Please configure option: \"{0}\" in section: \"miner\"'.format(opt))
            sys.exit(0)
    return conf

def _gen_conf(config_file_name, miner_name):
    '''Generate config'''
    conf = configparser.ConfigParser()
    for key in vars(args):
        if key == 'config':
            continue
        key_tmp = key.split('_')
        section = key_tmp[0]
        section_key = '_'.join(key_tmp[1:])
        if section not in conf:
            conf[section] = dict()
        conf[section][section_key] = vars(args)[key]
    for key in miner_options[miner_name]['options']:
        conf['miner'][key] = 'change_me'
    with open(config_file_name, 'w') as config_file:
        conf.write(config_file)
    print('Default config generated, you able to customize it via command:\neditor config.ini')
    sys.exit(0)

def write_pid():
    '''Write main process PID to file'''
    with open(conf['supervisor']['pid_file'], 'w') as pid:
        pid.write(str(os.getpid()))

def run_proc(proc_name):
    '''Run proc'''
    root_dir = os.path.dirname(os.path.abspath(__file__))
    miner_name = conf['miner']['name']
    os.chdir(root_dir)

    proc_paths = dict()
    proc_paths['miner'] = '{0}/build/{1}/{1} '.format(root_dir, miner_name)
    proc_paths['watchdog'] = os.path.join(root_dir, 'miner.py')
    proc_paths['api'] = os.path.join(root_dir, 'api', 'api.py')
    proc_paths['oc'] = os.path.join(root_dir, 'nvset.py')

    if proc_name == 'miner':
        command = proc_paths['miner'] + miner_options[miner_name]['template'].format(**conf['miner'])
    else:
        command = 'python3 {} {}'.format(proc_paths[proc_name], conf[proc_name]['options'])

   #command = shlex.split(command)
    command = command.split()

    proc_stdout=open('/tmp/{}.stdout'.format(proc_name), 'w')
    proc_stderr=open('/tmp/{}.stderr'.format(proc_name), 'w')
    proc = Popen(command, stdout=proc_stdout, stderr=proc_stderr)
    print('Process \"{0}\" started'.format(proc_name))
    return proc

if __name__ == '__main__':
    conf = parse_configuration(args)
    write_pid()
    # run services
    for service_name in ['api', 'oc', 'miner', 'watchdog']:
        run_proc(service_name)
    while True:
        time.sleep(1)

