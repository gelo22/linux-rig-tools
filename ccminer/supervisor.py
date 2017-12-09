#!/usr/bin/env python3

import os
import time
import sys
from subprocess import Popen, PIPE
import traceback
import argparse
import datetime
import signal
import configparser

def parse_configuration():
    '''Parse configuration from config and cmd'''
    # parse args
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='config file location')
    args = parser.parse_args()
    # init config
    conf = configparser.ConfigParser()
    # get config from file
    conf.read(args.config)
    # add parsed args to conf
    for key in vars(args):
        if vars(args)[key]:
            conf['supervisor'][key] = vars(args)[key]
    return conf

def fork():
    '''Fork process if daemon mode'''
    if conf['supervisor']['daemon'] == 'yes':
        if os.fork():
            sys.exit()

def write_pid():
    '''Write main process PID to file'''
    with open(conf['supervisor']['pid_file'], 'w') as pid:
        pid.write(str(os.getpid()))

def open_log():
    '''Open main log file'''
    if conf['supervisor']['log_level'] == 'stdout':
        log_file = sys.stdout
    else:
        log_file = open(conf['supervisor']['log_file'], 'w')
    return log_file

def do_log(message, level):
    '''
    Write logs to file or stdout - regarding to log level
    Can write to output via appropriate config option
    '''
    levels = { 'none': 0, 'info': 1, 'warn': 2, 'debug': 3 }
    current_time = datetime.datetime.now()
    if conf['supervisor']['log_level'] == 'stdout':
        message = '{0} {1}\n'.format(current_time, str(message).strip())
        log_file.write(message)
        log_file.flush()
        return
    level_weight = levels[level]
    conf_level_weight = levels[conf['supervisor']['log_level']]
    if conf_level_weight >= level_weight:
        message = '{0} {1}: {2}\n'.format(datetime.datetime.now(), level.upper(), str(message).strip())
        log_file.write(message)
        log_file.flush()

def check_proc_alive(pid, command):
    '''Check if pid match to command'''
    # cmdline contain full command, splited by null bytes, in the end - final null byte
    current_command = ' '.join(open('/proc/{0}/cmdline'.format(pid)).read().split('\x00')[:-1])
    if current_command == str(command):
        return True
    else:
        print(current_command)
        print(command)
        return False

def watchdog(proc):
    '''Watchdog which check proc health'''
    if not proc or not check_proc_alive(proc.pid, ' '.join(proc.args)):
        return False
    else:
        return True
    
def run_proc(proc_name):
    '''Run proc'''
    template = '{0} {1}'
    command = template.format(conf[proc_name]['binary'],
                              conf[proc_name]['args']).split()

    proc_stdout=open(conf[proc_name]['stdout_log_file'], 'w')
    proc_stderr=open(conf[proc_name]['stderr_log_file'], 'w')
    proc = Popen(command, stdin=PIPE, stdout=proc_stdout, stderr=proc_stderr)
    return proc

def set_reload_daemon(signum, frame):
    '''Set reload status to True'''
    data['reload_daemon'] = True

def print_config():
    for section in conf.sections():
        for key in conf[section]:
            do_log('conf[{0}][{1}] = {2}'.format(section, key, conf[section][key]), 'debug')

if __name__ == '__main__':
    # first run things
    # add dictionary for data exchange
    data = { 'reload_daemon': False, 'procs': {'miner': '', 'api': ''} }
    # set reload signal and function for reload process
    signal.signal(1, set_reload_daemon)
    try:
        conf = parse_configuration()
        log_file = open_log()
        write_pid()
        print_config()
        fork()
        # run services
        for service in data['procs']:
            data['procs'][service] = run_proc(service)
    except:
        trace = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        try:
            do_log(str(trace), 'info')
        except:
            print(str(trace))

    # main loop, which always run fresh start after all threads exit
    while True:
        try:
            if data['reload_daemon']:
                data['reload_daemon'] = False
                do_log('Reloading daemon', 'info')
                conf = parse_configuration()
                log_file = open_log()
            time.sleep(int(conf['supervisor']['checks_delay']))
            for service_proc in data['procs']:
                if not watchdog(data['procs'][service_proc]):
                    data['procs'][service_proc] = run_proc(service_proc)
                    do_log('Process: {0} restarted'.format(service_proc), 'info')

        # stop if Ctrl + C
        except KeyboardInterrupt:
            sys.exit(0)
        # write all exceptions to log and keep going
        except:
            trace = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
            try:
                do_log(str(trace), 'info')
                time.sleep(int(conf['supervisor']['restart_delay']))
            except:
                print(str(trace))
                time.sleep(int(conf['supervisor']['restart_delay']))
         
