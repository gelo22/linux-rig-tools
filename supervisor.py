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
#parser.add_argument('--miner_options', default='-a lbry -o stratum+tcp://lbry.suprnova.cc:6256 -u one_miner.new -p x111 -i 25 --max-temp=75', help='Options for miner')
parser.add_argument('--watchdog_options', default='--minimal-hashrate 280 --debug --miner-api-port 3333', help='Options for watchdog')
parser.add_argument('--api_options', default='--api --gpu-type nvidia --getdata-interval 10', help='Options for api')
parser.add_argument('--oc_options', default='-c oc.ini -D', help='Options for oc')
args = parser.parse_args()

miner_options = {'ccminer': {'algorithm': '-a',
                             'pool': '-o',
                             'user': '-u',
                             'password': '-p',
                             'max_temperature': '--max-temp='
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
        _gen_conf(args.config)
    conf = configparser.ConfigParser()
    conf.read(args.config)
    return conf

def _gen_conf(config_file_name):
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
    for key in miner_options[conf['miner']['name']]:
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
    os.chdir(root_dir)
    proc_paths = dict()
    proc_paths['miner'] = '{0}/build/{1}/{1}'.format(root_dir, conf['miner']['name'])
    proc_paths['watchdog'] = os.path.join(root_dir, 'miner.py')
    proc_paths['api'] = os.path.join(root_dir, 'api', 'api.py')
    proc_paths['oc'] = os.path.join(root_dir, 'nvset.py')

    if proc_name == 'miner':
        command = proc_paths['miner']
        for opt in conf['miner']:
            if opt == 'name':
                continue
            if miner_options[conf['miner']['name']][opt][-1] == '=':
                command += ' {0}{1}'.format(miner_options[conf['miner']['name']][opt], conf['miner'][opt])
            else:
                command += ' {0} {1}'.format(miner_options[conf['miner']['name']][opt], conf['miner'][opt])
       #command = '{} {}'.format(proc_paths[proc_name], conf[proc_name]['options'])
    else:
        command = 'python3 {} {}'.format(proc_paths[proc_name], conf[proc_name]['options'])

    command = shlex.split(command)
   #command = command.split()
    print(command)
    return
    proc_stdout=open('/tmp/{}.stdout'.format(proc_name), 'w')
    proc_stderr=open('/tmp/{}.stderr'.format(proc_name), 'w')
    proc = Popen(command, stdout=proc_stdout, stderr=proc_stderr)
    return proc

if __name__ == '__main__':
    conf = parse_configuration(args)
    write_pid()
    # run services
    for service_name in ['api', 'oc', 'miner']:
        run_proc(service_name)
    while True:
        time.sleep(1)

