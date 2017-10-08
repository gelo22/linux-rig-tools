import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
import json
import re
import sys
import os
import subprocess
from collections import defaultdict
from pprint import pprint
from socket import timeout
import time
import logging as log
import argparse


parser = argparse.ArgumentParser(description='API client')

parser.add_argument('-s', '--server-list', type=str, nargs='+', default=['http://localhost:8000/api/v1', ])
parser.add_argument('-i', '--interval', type=int, default=2, help='Get data interval')
parser.add_argument('--show-host', action='store_true', default=False, help='Show host info')
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


API_KEYS = (
    'name', 'card_model', 'driver_version', 'bus_id',
    'temp', 'fan', 'power_current', 'power_max',
    'core_load', 'core_clock', 'mem_clock', 'mem_used', 'mem_total', 'vendor',
)


def print_table(data):
    j = json.loads(data)

    d = defaultdict(list)

    t_head = ('name', 'vendor')
    t_body = ('temp', 'fan', 'core_load', 'power_current', 'core_clock', 'mem_clock')

    for i in j:
        api_data = i.get('cards')

        for card in api_data:
            for key in card.keys():
                if key not in API_KEYS:
                    card[key] = 'null'
            card.update(dict(fill=' '))

            d['head'].append('+{}'.format('-' * 18))
            d['name'].append('| {name:17}'.format(**card))
            d['vendor'].append('| {vendor:16} '.format(**card))
            d['temp'].append('| temp:{fill:5}{temp:2} C{fill:3}'.format(**card))
            d['fan'].append('| fan:{fill:5}{fan:3} %{fill:3}'.format(**card))
            d['core_load'].append('| load:{fill:4}{core_load:3} %{fill:3}'.format(**card))
            d['power_current'].append('| power:{fill:3}{power_current:3} W{fill:3}'.format(**card))
            d['core_clock'].append('| core:{fill:3}{core_clock:4} Mhz '.format(**card))
            d['mem_clock'].append('| mem:{fill:4}{mem_clock:4} Mhz '.format(**card))

    for part in [t_head, t_body]:
        print_row(d, 'head')
        for k in part:
            print_row(d, k)
            if k == t_body[-1]:
                print_row(d, 'head', '\n')


def print_row(d, key, newline=''):
    end = '|'
    if key == 'head':
        end = '+'
    print('{data}{end}{newline}'.format(data=''.join(d[key]), end=end, newline=newline))


def get_stat():
    res = []

    for i in args.server_list:
        o = urlparse(i)
        host, port = o.scheme, o.port
        url = o.geturl()

        try:
            resp = urllib.request.urlopen(url, timeout=2).read().decode('utf-8')
        except (HTTPError, URLError) as error:
            log.error('Data is not retrieved. Error: {}\nURL: {}\n'.format(error, url))
        except timeout:
            log.error('Time out. URL: {}\n'.format(url))
        else:
            if args.show_host:
                log.info('Host: {}'.format(o.netloc))
                log.info('API url: {}'.format(url))
            print_table(resp)


if args.daemon:
    while True:
        get_stat()
        time.sleep(args.interval)
else:
    get_stat()
