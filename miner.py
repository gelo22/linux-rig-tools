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


parser = argparse.ArgumentParser(description='Miner run tool')
parser.add_argument('--minimal-hashrate', type=int, required=True, help='Miner minimal hashrate')
parser.add_argument('--hashrate-delta-reboot', type=int, default=15)
parser.add_argument('--miner-api-host', type=str, default='localhost', help='Miner API host')
parser.add_argument('--miner-api-port', type=int, default=3333, help='Miner API port')
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
    log_fp = os.path.join(ROOT_DIR, 'error.log')
    ts = datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S')
    d = defaultdict(list)
    log_list = []

    for line in dmesg_out.decode('utf-8').split('\n'):
        m = re.match(regex, line)
        if m:
            key = m.group('bus_id')
            d[key].append(line)

    for k in d.keys():
        err_msg = '[{}] GPU error on bus_id \"{}\"'.format(ts, k)
        log.error(err_msg)
        log_list.append(err_msg)
        log_list.append('Raw log:')
        for l in d[k]:
            log_list.append('  {}'.format(l))
        log_list.append('\n')
    log_list.append('=' * 16)

    write_file(log_fp, log_list, mode='a', debug=True, sync=True)


class EthMiner():
    def __init__(self, minimal_hashrate, host, port):
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

    def sys_reboot(self, delay=args.sys_reboot_delay):
        parse_dmesg()

        log.warning('System reboot in {} seconds ...'.format(delay))
        time.sleep(delay)
        os.system('sudo reboot -dnf')

    def fix_types(self):
        self.miner_uptime = int(self.miner_uptime)
        self.valid, self.rejected = int(self.valid), int(self.rejected)
        self.total_hashrate = round(int(self.total_hashrate) / 1000, 2)


eth_miner = EthMiner(
    minimal_hashrate=args.minimal_hashrate,
    host=args.miner_api_host, port=args.miner_api_port
)


while True:
    eth_miner.watchdog()
    time.sleep(1)
