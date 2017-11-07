from app.core import check_python

check_python()

from collections import OrderedDict, defaultdict
import os
import sys
import json
import time
import logging as log
import argparse
import datetime
import configparser

from app.core import run_proc, read_api, check_port, write_file
from app.settings import API_URL


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

MINER = dict(
    ethminer=dict(class_name='EthMiner', port=3333, url='/'),
    ewbf=dict(class_name='EwbfMiner', port=42000, url='getstat'),
)
MINER_CHOICES = list(MINER.keys())
MINER_DEFAULT = MINER_CHOICES[0]


parser = argparse.ArgumentParser(description='Miner run tool')
parser.add_argument('--minimal-hashrate', type=int, required=True, help='Miner minimal hashrate')
parser.add_argument('--hashrate-delta-reboot', type=int, default=15)
parser.add_argument('--miner-name', type=str, choices=MINER_CHOICES, default=MINER_DEFAULT, help='Miner name')
parser.add_argument('--miner-api-host', type=str, default='localhost', help='Miner API host')
parser.add_argument('--miner-api-port', type=int, required=False, help='Miner API port')
parser.add_argument('--sys-reboot-delay', type=int, default=60)
parser.add_argument('--debug', action='store_true', default=False, help='Debug mode')


args = parser.parse_args()

if args.debug:
    LOG_LEVEL = log.DEBUG
else:
    LOG_LEVEL = log.INFO

log.basicConfig(format='[%(levelname)s] %(message)s', level=LOG_LEVEL)


def parse_dmesg():
    import re

    regex = r'.*NVRM\:\sXid\s\(PCI\:(?P<bus_id>\w+\:\w{2}\:\w{2})\)\:'
    dmesg_out = run_proc('dmesg')
    d = defaultdict(list)

    for line in dmesg_out.decode('utf-8').split('\n'):
        m = re.match(regex, line)
        if m:
            key = m.group('bus_id')
            d[key].append(line)
    return d


def write_log(d):
    ts = datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S')
    log_fp = os.path.join(ROOT_DIR, 'error.log')
    log_list = []

    for k in d.keys():
        err_msg = '[{}] GPU error on bus_id \"{}\"'.format(ts, k)
        log.error(err_msg)
        log_list.append(err_msg)
        log_list.append('Raw log:')
        for l in d[k]:
            log_list.append('  {}'.format(l))
        log_list.append('\n')

    if log_list:
        log_list.append('=' * 16)
        write_file(log_fp, log_list, mode='a', debug=True, sync=True)
    else:
        log.warning('Nothing to log')


def get_json_data(*args, **kw):
    from socket import timeout
    import urllib.request
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlparse, urljoin

    o = urlparse('http://{host}:{port}/{url}'.format(**kw))
    host, port = o.scheme, o.port
    url = o.geturl()
    resp = None

    try:
        resp = urllib.request.urlopen(url, timeout=2).read().decode('utf-8')
    except (HTTPError, URLError) as error:
        log.error('Data is not retrieved. Error: {}\nURL: {}\n'.format(error, url))
    except timeout:
        log.error('Time out. URL: {}\n'.format(url))
    return resp


class BaseMiner():
    def sys_reboot(self, delay=args.sys_reboot_delay, fake=False):
        cmd = 'sudo reboot -dnf'
        write_log(parse_dmesg())

        log.warning('System reboot in {} seconds ...'.format(delay))
        time.sleep(delay)
        if not fake:
            os.system(cmd)
        else:
            log.debug(cmd)


class EthMiner(BaseMiner):
    def __init__(self, minimal_hashrate, host, port, url=''):
        self.host = host
        self.port = port
        self.minimal_hashrate = minimal_hashrate

        self.ETHMINER_API_KEYS = ('stat', 'restart')
        self.ETHMINER_API_VALUES = ('miner_getstat1', 'miner_restart')
        self.ETHMINER_API = dict(zip(self.ETHMINER_API_KEYS, self.ETHMINER_API_VALUES))
        self.ETHMINER_TPL = dict(method='', jsonrpc='2.0', id=0)

        self.HASHRATE_STAT = []
        self.HASHRATE_EMPTY = []
        self.HASHRATE_STAT_SAMPLES = 16

        self.watchdog_uptime = 0
        self.watchdog_start_time = datetime.datetime.now()

        self.timer1_prev = datetime.datetime.now()
        self.timer1_now = datetime.datetime.now()

        self.total_hashrate = 0
        self.valid = 0
        self.rejected = 0
        self.miner_uptime = 0
        self.average_hashrate = 0
        self.share_rate = 0

    def send_json(self, action, nc_delay=1):
        out = None

        if action in self.ETHMINER_API.keys():
            self.ETHMINER_TPL.update(dict(method=self.ETHMINER_API.get(action)))
            eth_kw = dict(
                json_data=json.dumps(self.ETHMINER_TPL),
                host=self.host,
                port=self.port,
                nc_delay=nc_delay
            )
            eth_cmd = 'echo \'{json_data}\' | nc {host} {port} -w {nc_delay}'.format(**eth_kw)
            out = run_proc(eth_cmd)

        if out:
            data = json.loads(out.decode('utf-8'))['result']
            log.debug(eth_cmd)
            log.debug(data)
            return data
        else:
            log.error('No connection with miner API {}:{}'.format(self.host, self.port))
            return None

    def watchdog(self):
        self.timer1_now = datetime.datetime.now()
        self.watchdog_uptime = int((datetime.datetime.now() - self.watchdog_start_time).seconds / 60)

        miner_data = self.send_json(action=self.ETHMINER_API_KEYS[0])

        stat_isfull = len(self.HASHRATE_STAT) > self.HASHRATE_STAT_SAMPLES
        empty_isfull = len(self.HASHRATE_EMPTY) > self.HASHRATE_STAT_SAMPLES

        if (self.timer1_now - self.timer1_prev).seconds > 60:
            self.timer1_prev = datetime.datetime.now()
            pass

        if stat_isfull:
            self.HASHRATE_STAT.pop(0)
        if self.watchdog_uptime >= 1 and self.total_hashrate > 0:
            self.HASHRATE_STAT.append(self.total_hashrate)

        try:
            self.average_hashrate = round(sum(self.HASHRATE_STAT) / len(self.HASHRATE_STAT), 2)
            self.share_rate = round(self.valid / self.miner_uptime, 2)
        except ZeroDivisionError as e:
            log.error(e)

        if miner_data:
            self.version, self.miner_uptime = miner_data[0], miner_data[1]
            self.total_hashrate, self.valid, self.rejected = miner_data[2].split(';')
            self.fix_types()
        else:
            if self.watchdog_uptime >= 1:
                self.HASHRATE_EMPTY.append(1)

        if all([stat_isfull, self.average_hashrate < self.minimal_hashrate, self.valid > 10]):
            log.warning('Average hashrate {} lower than {}'.format(self.average_hashrate, self.minimal_hashrate))
            self.sys_reboot()

        if all([self.watchdog_uptime >= 3, empty_isfull]):
            log.error('Miner is down!')
            self.sys_reboot(30)

        if args.debug:
            log.debug(self.HASHRATE_STAT)
            log.debug(self.HASHRATE_EMPTY)

            if miner_data:
                miner_stat = [
                    self.version, str(self.miner_uptime),
                    str(self.total_hashrate), str(self.valid), str(self.rejected)
                ]
                log.debug('Miner version: {}, uptime: {}, current hashrate: {}, valid: {}, rejected: {}'.format(*miner_stat))
            log.info('Watchdog uptime: {}'.format(self.watchdog_uptime))
            log.info('Average hashrate: {}; Minimal reboot hashrate: {}; Share rate: {}/min\n'.format(self.average_hashrate, self.minimal_hashrate, self.share_rate))

    def fix_types(self):
        self.miner_uptime = int(self.miner_uptime)
        self.valid, self.rejected = int(self.valid), int(self.rejected)
        self.total_hashrate = round(int(self.total_hashrate) / 1000, 2)


class EwbfMiner(BaseMiner):
    def __init__(self, minimal_hashrate, host, port, url=''):
        self.host = host
        self.port = port
        self.url = url
        self.minimal_hashrate = minimal_hashrate

        self.watchdog_uptime = 0
        self.watchdog_start_time = datetime.datetime.now()

        self.miner_data = {}
        self.miner_data_ts = datetime.datetime.now()
        self.HASHRATE_EMPTY = []
        self.HASHRATE_STAT_SAMPLES = 16

        self.cur_hashrate = 0
        self.total_power = 0
        self.miner_start_time = datetime.datetime.now()

    def get_data(self):
        self.miner_data_ts_delta = datetime.datetime.now() - self.miner_data_ts
        data = get_json_data(host=self.host, port=self.port, url=self.url)

        if data:
            data = json.loads(data)
            result = data.get('result')

            self.cur_hashrate = sum([x.get('speed_sps') for x in result])
            self.total_power = sum([x.get('gpu_power_usage') for x in result])
            self.total_accepted = sum([x.get('accepted_shares') for x in result])
            self.total_rejected = sum([x.get('rejected_shares') for x in result])
            self.miner_start_time = datetime.datetime.fromtimestamp(data.get('start_time'))
            self.miner_data_ts = datetime.datetime.now()
            self.miner_data = {x.get('busid'):
                dict(
                    hashrate=x.get('speed_sps'), busid=x.get('busid'), name=x.get('name'),
                    accepted=x.get('accepted_shares'), rejected=x.get('rejected_shares'),
                ) for x in result}
            log.info('Miner API is alive')
            log.info(self.miner_data)
            log.debug(data)
            log.info('Total hashrate: {} Sol/sec; Total power: {} W'.format(self.cur_hashrate, self.total_power))
            log.info('Accepted: {}; Rejected {}\n'.format(self.total_accepted, self.total_rejected))
        else:
            data = None
            self.miner_data = {}
            log.error('Miner API is down?')
        return data

    def watchdog(self):
        self.watchdog_uptime = int((datetime.datetime.now() - self.watchdog_start_time).seconds)
        self.get_data()

        log.info('Miner get_data ts (delta seconds): {}'.format(self.miner_data_ts_delta.seconds))

        if self.watchdog_uptime >= 3 * 60:
            if self.cur_hashrate < self.minimal_hashrate:
                log.warning('Current hashrate {} < {} (minimal hashrate)'.format(self.cur_hashrate, self.minimal_hashrate))
                self.HASHRATE_EMPTY.append(1)
                log.warning(self.HASHRATE_EMPTY)
            else:
                self.HASHRATE_EMPTY = []

            if any([self.miner_data_ts_delta.seconds >= (3 * 60), len(self.HASHRATE_EMPTY) >= self.HASHRATE_STAT_SAMPLES]):
                self.sys_reboot(30)


miner_d = MINER.get(args.miner_name)
miner_class_name = miner_d.get('class_name')
if not args.miner_api_port:
    miner_port = miner_d.get('port')
else:
    miner_port = args.miner_api_port
miner_class = eval(miner_class_name)
miner_url = miner_d.get('url')


miner = miner_class(
    minimal_hashrate=args.minimal_hashrate,
    host=args.miner_api_host, port=miner_port, url=miner_url,
)


while True:
    miner.watchdog()
    time.sleep(1)
