from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import argparse
import logging as log
import json
import os
import sys
import subprocess
import random
from pprint import pprint


GPU_TYPE = ['amd', 'nvidia']

parser = argparse.ArgumentParser(description='Miner API')

parser.add_argument('--api', action='store_true', default=False, help='Start API server')
parser.add_argument('--gpu-type', type=str, action='store', required=True, choices=GPU_TYPE)
parser.add_argument('--debug', action='store_true', default=False)
parser.add_argument('--fake', action='store_true', default=False, help='Test mode, enable fake data')


args = parser.parse_args()


if args.debug:
    DEBUG = True
    LOG_LEVEL = log.DEBUG
else:
    DEBUG = False
    LOG_LEVEL = log.INFO

log.basicConfig(format='[%(levelname)s] %(message)s', level=LOG_LEVEL)


class NvidiaGpu():
    def __init__(self):
        self.cards_data = []
        self.cards_keys = (
            'index', 'card_model', 'uuid', 'driver_version', 'bus_id', 'pcie_gen',
            'core_load', 'temp', 'fan', 'power_current', 'core_clock', 'mem_clock',
            'mem_load', 'mem_used', 'mem_total',
            'vbios_version',
        )
        self.smi_keys = (
            'index', 'name', 'uuid', 'driver_version', 'pci.bus_id', 'pcie.link.gen.current',
            'utilization.gpu', 'temperature.gpu', 'fan.speed', 'power.draw', 'clocks.sm', 'clocks.mem',
            'utilization.memory', 'memory.used', 'memory.total',
            'vbios_version',
        )
        self.nvidia_smi = (
            'nvidia-smi',
            '--query-gpu={}'.format(','.join(self.smi_keys)),
            '--format=csv'
        )

    def get_data(self):
        if args.fake:
            log.info(' '.join(self.nvidia_smi))

        proc = subprocess.Popen(self.nvidia_smi, stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()
        for card in proc[0].decode('utf-8').split('\n'):
            if card:
                d = dict(zip(self.cards_keys, card.split(', ')))
                index = d.get('index')

                if index == 'index':
                    continue

                index = int(index)
                d.update(dict(
                    index=index,
                    name='card{0:02d}'.format(index),
                    temp=int(d.get('temp')),
                    power_current=round(float(d.get('power_current').split(' ')[0])),
                    mem_load=int(d.get('mem_load').split(' ')[0]),
                    core_load=int(d.get('core_load').split(' ')[0]),
                    core_clock=int(d.get('core_clock').split(' ')[0]),
                    mem_used=int(d.get('mem_used').split(' ')[0]),
                    mem_total=int(d.get('mem_total').split(' ')[0]),
                    mem_clock=int(d.get('mem_clock').split(' ')[0]),
                    fan=int(d.get('fan').split(' ')[0]),
                    vendor=GPU_TYPE[1],
                ))

                self.cards_data.append(d)
        log.debug(self.cards_data)
        return self.cards_data


class AmdGpu():
    def __init__(self):
        self.cards_data = []
        self.cards_keys = ('name', 'temp_path', 'pwm_path', 'temp', 'pwm', 'fan')
        self.sysfs_path = '/sys/class/drm/'
        self.sysfs_temp = 'temp1_input'
        self.sysfs_pwm = 'pwm1'
        self.card_path_tpl = '/sys/class/drm/card{card_id}/device/hwmon/hwmon{hw}/{data_type}'
        self.card_kernel_path_tpl = '/sys/kernel/debug/dri/{card_id}/amdgpu_pm_info'

    def get_data(self):
        """
        Tested on AMDGPU-PRO driver
        """
        import re
        import os

        card_id_list = []


        regex = r'^card(?P<card_id>[\d]+)$'

        if args.fake:
            card_list = (
                'card3-HDMI-A-5', 'card3-HDMI-A-6', 'card4', 'card4-DP-11', 'card4-DP-12',
                'card4-DP-13', 'card4-DVI-D-5', 'card4-HDMI-A-7', 'card5', 'card5-DP-14',
                'card5-DP-15', 'card5-DP-16', 'card5-DVI-D-6', 'card5-HDMI-A-8', 'card6',
                'card6-DP-17', 'card6-DP-18', 'card6-DP-19', 'card6-DVI-D-7', 'card6-HDMI-A-9',
                'card7', 'card7-DP-20', 'card0', 'card0-DP-1', 'card0-DP-2', 'card0-DVI-D-1',
                'card12-HDMI-A-10', 'card12-HDMI-A-3', 'card12', 'card12-DP-6', 'card12-DP-7',
                'card0-HDMI-A-1', 'card0-HDMI-A-2', 'card1', 'card1-DP-3', 'card1-DP-4',
                'card1-DP-5', 'card1-DVI-D-2', 'card7-DP-21', 'card7-DP-22', 'card7-DVI-D-8',
                'card7-HDMI-A-10', 'card1-HDMI-A-3', 'card2', 'card2-DP-6', 'card2-DP-7',
                'card2-DP-8', 'card2-DVI-D-3', 'card2-HDMI-A-4', 'card3', 'card3-DP-10',
                'card3-DP-9', 'card3-DVI-D-4', 'renderD128', 'renderD129', 'renderD130',
                'card10-HDMI-A-10', 'card10-HDMI-A-3', 'card10', 'card10-DP-6', 'card10-DP-7',
                'renderD131', 'renderD132', 'renderD133', 'renderD134', 'renderD135', 'version',
            )
        else:
            try:
                card_list = [x for x in os.listdir(self.sysfs_path) if 'card' in x]
            except FileNotFoundError:
                log.error('Error reading \"{}\"'.format(self.sysfs_path))
                card_list = []

        for card in sorted(card_list):
            m = re.match(regex, card)
            if m:
                card_id = int(m.group('card_id'))
                card_id_list.append(card_id)

        card_id_list.sort()

        card_names = ['card{0:02d}'.format(x) for x in card_id_list]
        temp_path_list = [self.card_path_tpl.format(card_id=x, hw=x + 1, data_type=self.sysfs_temp) for x in card_id_list]
        temp_values = self.read_data(temp_path_list)

        pwm_path_list = [self.card_path_tpl.format(card_id=x, hw=x + 1, data_type=self.sysfs_pwm) for x in card_id_list]
        pwm_values = self.read_data(pwm_path_list)
        fan_values = [self.pwm2fan(x) for x in pwm_values]

        kernel_values = self.read_kernel_data(card_id_list)

        for idx, i in enumerate(zip(card_names, temp_path_list, pwm_path_list, temp_values, pwm_values, fan_values)):
            d = dict(zip(self.cards_keys, i))
            d['vendor'] = GPU_TYPE[0]
            d.update(kernel_values[idx])
            self.cards_data.append(d)

        log.debug(self.cards_data)
        return self.cards_data

    def pwm2fan(self, pwm):
        return round(int(pwm) / (255 / 100))

    def read_data(self, path_list):
        res = []

        for path in path_list:
            if not args.fake:
                with open(path, 'r') as f:
                    try:
                        data = int(f.read().rstrip())
                        if self.sysfs_temp in path:
                            data = round(data / 1000)
                        res.append(data)
                    except:
                        log.error('Error reading \"{}\"'.format(path))
            else:
                if self.sysfs_temp in path:
                    fake_data = random.randint(20, 75)
                else:
                    fake_data = random.randint(0, 255)
                res.append(fake_data)
        return res

    def read_kernel_data(self, id_list):
        res = []

        for cid in id_list:
            path = self.card_kernel_path_tpl.format(card_id=cid)
            d = dict()

            if os.path.exists(path) and os.path.isfile(path):
                with open(path, 'r') as f:
                    for i in f.readlines():
                        if 'GPU Load:' in i:
                            d['core_load'] = int(i.split(' ')[2])
                        if '(average GPU)' in i:
                            d['power_current'] = round(float(i.split()[0]))
                        if '(MCLK)' in i:
                            d['mem_clock'] = int(i.split()[0])
                        if '(SCLK)' in i:
                            d['core_clock'] = int(i.split()[0])
                        if '(max GPU)' in i:
                            d['power_max'] = round(float(i.split()[0]))
                log.debug(path)
                res.append(d)
            else:
                log.error('Error reading \"{}\". Maybe need root access'.format(path))
        log.debug(res)
        return res


def get_api_data():
    if args.gpu_type == GPU_TYPE[0]:
        gpu_data = AmdGpu()
    elif args.gpu_type == GPU_TYPE[1]:
        gpu_data = NvidiaGpu()

    data = [
        dict(cards=gpu_data.get_data()),
    ]

    if args.fake:
        data.append(dict(fake=True))
    log.debug(data)
    return data


class HttpRequestHandler(BaseHTTPRequestHandler):
    def _send_html(self, http_code, html):
        self.send_response(http_code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def _send_json(self, data):
        try:
            res = json.dumps(data)
        except:
            self.send_response(500)
            return

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(res.encode('utf-8'))

    def do_GET(self):
        if self.path == '/api/v1':
            self._send_json(get_api_data())
        else:
            self._send_html(200, '<h1>It works!</h1>')


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    def __init__(self, _host, _handler):
        super().__init__(_host, _handler)
        self.daemon_threads = True


if args.api:
    log.info('Server listening on port 8000...')
    httpd = ThreadedHTTPServer(('0.0.0.0', 8000), HttpRequestHandler)
    httpd.serve_forever()
else:
    if args.gpu_type == GPU_TYPE[0]:
        a = AmdGpu()
        a.get_data()
    elif args.gpu_type == GPU_TYPE[1]:
        n = NvidiaGpu()
        n.get_data()
