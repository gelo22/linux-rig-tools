from app.core import check_python

check_python()

from collections import OrderedDict
import os
import sys
import json
import time
import logging as log
import argparse
import configparser

from app.core import run_proc, read_api, check_port
from app.settings import API_URL


parser = argparse.ArgumentParser(description='Miner run tool')
parser.add_argument('--minimal-hashrate', type=int, required=True, help='Miner minimal hashrate')
parser.add_argument('--hashrate-delta-reboot', type=int, default=15)
parser.add_argument('--miner-api-host', type=str, default='localhost', help='Miner API host')
parser.add_argument('--miner-api-port', type=int, default=3333, help='Miner API port')
parser.add_argument('--debug', action='store_true', default=False, help='Debug mode')


args = parser.parse_args()

if args.debug:
    LOG_LEVEL = log.DEBUG
else:
    LOG_LEVEL = log.INFO

log.basicConfig(format='[%(levelname)s] %(message)s', level=LOG_LEVEL)


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

        self.reset_data()

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
            self.reset_data()
            return None

    def reset_data(self):
        self.total_hashrate = 0
        self.valid = 0
        self.rejected = 0
        self.miner_uptime = 0
        self.average_hashrate = 0
        self.share_rate = 0

    def watchdog(self):
        miner_data = self.send_json(action=self.ETHMINER_API_KEYS[0])

        stat_isfull = len(self.HASHRATE_STAT) > self.HASHRATE_STAT_SAMPLES
        empty_isfull = len(self.HASHRATE_EMPTY) > self.HASHRATE_STAT_SAMPLES

        if stat_isfull:
            self.HASHRATE_STAT.pop(0)
        if self.total_hashrate > 0:
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
            self.HASHRATE_EMPTY.append(1)

        if all([stat_isfull, self.average_hashrate < self.minimal_hashrate, self.valid > 10]):
            self.HASHRATE_STAT = []
            reboot_delay = 30
            log.warning('System reboot in {} seconds ...'.format(reboot_delay))
            time.sleep(reboot_delay)
            os.system('sudo reboot -dnf')

        if args.debug:
            log.debug(self.HASHRATE_STAT)
            log.debug(self.HASHRATE_EMPTY)

            if miner_data:
                miner_stat = [
                    self.version, str(self.miner_uptime),
                    str(self.total_hashrate), str(self.valid), str(self.rejected)
                ]
                log.debug('Miner version: {}, uptime: {}, current hashrate: {}, valid: {}, rejected: {}'.format(*miner_stat))
            log.info('Average hashrate: {}; Minimal reboot hashrate: {}; Share rate: {}/min\n'.format(self.average_hashrate, self.minimal_hashrate, self.share_rate))

    def fix_types(self):
        self.miner_uptime = int(self.miner_uptime)
        self.valid, self.rejected = int(self.valid), int(self.rejected)
        self.total_hashrate = round(int(self.total_hashrate) / 1000, 2)

    def parse_dmesg(self):
        pass


eth_miner = EthMiner(
    minimal_hashrate=args.minimal_hashrate,
    host=args.miner_api_host, port=args.miner_api_port
)


while True:
    eth_miner.watchdog()
    time.sleep(1)
