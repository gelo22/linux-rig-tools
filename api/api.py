from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import argparse
import logging as log
import json
import os
import subprocess
import random
from pprint import pprint


parser = argparse.ArgumentParser(description='Miner API')

parser.add_argument('--api', action='store_true', default=False, help='Start API server')
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


class AmdGpuData():
    def __init__(self):
        self.cards_data = []
        self.sysfs_path = '/sys/class/drm/'
        self.sysfs_temp = 'temp1_input'
        self.sysfs_pwm = 'pwm1'

    def get_path_list(self):
        """
        Tested on AMDGPU-PRO driver
        """
        import re
        import os

        card_id_list = []
        card_path_tpl = '/sys/class/drm/card{card_id}/device/hwmon/hwmon{hw}/{data_type}'

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

        card_keys = ['card{0:02d}'.format(x) for x in card_id_list]
        temp_path_list = [card_path_tpl.format(card_id=x, hw=x + 1, data_type=self.sysfs_temp) for x in card_id_list]
        temp_values = self.read_data(temp_path_list)

        pwm_path_list = [card_path_tpl.format(card_id=x, hw=x + 1, data_type=self.sysfs_pwm) for x in card_id_list]
        pwm_values = self.read_data(pwm_path_list)
        fan_values = [self.pwm2fan(x) for x in pwm_values]

        r = []

        res_keys = ('name', 'temp_path', 'pwm_path', 'temp', 'pwm', 'fan')
        for i in zip(card_keys, temp_path_list, pwm_path_list, temp_values, pwm_values, fan_values):
            r.append(dict(zip(res_keys, i)))

        log.debug(r)
        self.cards_data = r
        return r

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


def get_data():
    amd_data = AmdGpuData()
    data = [
        dict(cards=amd_data.get_path_list()),
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
            self._send_json(get_data())
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
    a = AmdGpuData()
    a.get_path_list()
