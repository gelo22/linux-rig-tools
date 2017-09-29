import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
import json
import re
import sys
import os
import subprocess
from pprint import pprint
from socket import timeout
import time
import logging as log
import argparse


parser = argparse.ArgumentParser(description='API client')

parser.add_argument('-s', '--server-list', type=str, nargs='+', required=True)
parser.add_argument('-i', '--interval', type=int, default=2, help='Get data interval')
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


def print_table(data):
    j = json.loads(data)

    head = []
    k = []
    v_temp = []
    v_fan = []
    v_power_current = []
    v_core_load = []
    v_core_clock = []
    v_mem_clock = []
    v_ven = []

    for i in j:
        for card in i.get('cards'):
            card.update(dict(fill=' '))
            head.append('+{}'.format('-' * 18))
            k.append('| {name:17}'.format(**card))
            v_temp.append('| temp:{fill:5}{temp:2} C{fill:3}'.format(**card))
            v_fan.append('| fan:{fill:6}{fan:2} %{fill:3}'.format(**card))
            v_core_load.append('| load:{fill:4}{core_load:3} %{fill:3}'.format(**card))
            v_power_current.append('| power:{fill:3}{power_current:3} W{fill:3}'.format(**card))
            v_core_clock.append('| core:{fill:3}{core_clock:4} Mhz '.format(**card))
            v_mem_clock.append('| mem:{fill:4}{mem_clock:4} Mhz '.format(**card))
            v_ven.append('| {vendor:16} '.format(**card))
    print(''.join(head)   + '+')
    print(''.join(k)      + '|')
    print(''.join(v_ven)  + '|')
    print(''.join(head)   + '+')
    print(''.join(v_core_load) + '|')
    print(''.join(v_power_current) + '|')
    print(''.join(v_core_clock) + '|')
    print(''.join(v_mem_clock) + '|')
    print(''.join(v_temp) + '|')
    print(''.join(v_fan)  + '|')
    print(''.join(head)   + '+\n')


def get_stat():
    res = []

    for i in args.server_list:
        o = urlparse(i)
        host, port = o.scheme, o.port
        url = o.geturl()

        try:
            resp = urllib.request.urlopen(url, timeout=2).read()
        except (HTTPError, URLError) as error:
            log.error('Data is not retrieved. Error: {}\nURL: {}\n'.format(error, url))
        except timeout:
            log.error('Time out. URL: {}\n'.format(url))
        else:
            log.info('Host: {}'.format(o.netloc))
            log.info('API url: {}'.format(url))
            print_table(resp)


if args.daemon:
    while True:
        get_stat()
        time.sleep(args.interval)
else:
    get_stat()
