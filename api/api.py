from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import argparse
import logging as log
import json
import os
import subprocess
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


def get_data():
    data = [
        dict(cards=get_amd_cards()),
        dict(test_data=[1, 2, 3, 4, 5]),
    ]
    log.debug(data)
    return data


def get_amd_cards():
    """
    Tested on AMDGPU-PRO driver
    """
    import re
    import os

    pwm_list = []
    temp_list =[]
    card_path_tpl = '/sys/class/drm/card{card_id}/device/hwmon/hwmon{hw}/{data_type}'

    regex = r'^card(?P<card_id>[\d]+)$'

    if args.fake:
        card_list = (
            'card3-HDMI-A-5', 'card3-HDMI-A-6', 'card4', 'card4-DP-11', 'card4-DP-12',
            'card4-DP-13', 'card4-DVI-D-5', 'card4-HDMI-A-7', 'card5', 'card5-DP-14',
            'card5-DP-15', 'card5-DP-16', 'card5-DVI-D-6', 'card5-HDMI-A-8', 'card6',
            'card6-DP-17', 'card6-DP-18', 'card6-DP-19', 'card6-DVI-D-7', 'card6-HDMI-A-9',
            'card7', 'card7-DP-20', 'card0', 'card0-DP-1', 'card0-DP-2', 'card0-DVI-D-1',
            'card0-HDMI-A-1', 'card0-HDMI-A-2', 'card1', 'card1-DP-3', 'card1-DP-4',
            'card1-DP-5', 'card1-DVI-D-2', 'card7-DP-21', 'card7-DP-22', 'card7-DVI-D-8',
            'card7-HDMI-A-10', 'card1-HDMI-A-3', 'card2', 'card2-DP-6', 'card2-DP-7',
            'card2-DP-8', 'card2-DVI-D-3', 'card2-HDMI-A-4', 'card3', 'card3-DP-10',
            'card3-DP-9', 'card3-DVI-D-4', 'renderD128', 'renderD129', 'renderD130',
            'renderD131', 'renderD132', 'renderD133', 'renderD134', 'renderD135', 'version',
        )
    else:
        card_list = [x for x in os.listdir('/sys/class/drm/') if 'card' in x]

    for card in sorted(card_list):
        m = re.match(regex, card)
        if m:
            card_id = int(m.group('card_id'))
            pwm_path = card_path_tpl.format(card_id=card_id, hw=card_id + 1, data_type='pwm1')
            temp_path = card_path_tpl.format(card_id=card_id, hw=card_id + 1, data_type='temp1_input')
            pwm_list.append(pwm_path)
            temp_list.append(temp_path)

    r = {'temp': sorted(temp_list), 'pwm': sorted(pwm_list)}
    log.debug(r)
    return r


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
    get_amd_cards()
