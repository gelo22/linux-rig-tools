import os
import sys
import logging as log
import time
from pprint import pprint

from .settings import API_URL, API_TIMEOUT, DEBUG


log.basicConfig(format='[%(levelname)s] %(message)s', level=log.DEBUG)


def check_python():
    if sys.version_info[0] < 3:
        print('Please use Python 3\nExample: python3 {}'.format(sys.argv[0]))
        sys.exit(1)


def write_file(fp, text, mode='w', debug=False, sync=False):
    import os

    if type(text) == list:
        text = '\n'.join(text) + '\n'
    with open(fp, mode) as f:
        if debug:
            log.debug('Writing file \"{}\"'.format(fp))
        f.write(text)
        f.close()
    if sync:
        os.system('sync')


def run_proc(cmd_list, debug=False, fake=False):
    import subprocess

    if fake:
        return

    if type(cmd_list) == str:
        cmd_list = [cmd_list, ]

    for cmd in cmd_list:
        out, err = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()
        if debug:
            log.info(cmd)
            if out:
                log.warning(out.decode('utf-8').strip())
            if err:
                log.error(err.decode('utf-8').strip())
        return out


def check_md5(fp):
    import hashlib

    md5 = hashlib.md5(open(fp, 'rb').read()).hexdigest()
    log.debug('{} {}'.format(fp, md5))
    return md5


def check_config_file(fp):
    if not os.path.exists(fp):
        log.error('Config file \"{}\" not found'.format(fp))
        sys.exit(1)


def read_api(url=API_URL, debug=DEBUG, api_timeout=API_TIMEOUT):
    import urllib.request
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlparse
    from socket import timeout

    log.info('Reading API ...')

    try:
        resp = urllib.request.urlopen(url, timeout=api_timeout).read().decode('utf-8')
    except (HTTPError, URLError) as error:
        log.error('Data is not retrieved. Error: {}\nURL: {}\n'.format(error, url))
    except timeout:
        log.error('Time out. URL: {}\n'.format(url))
    else:
        j = json.loads(resp)
        if debug:
            pprint(j)
        return(j)


def check_port(host, port, debug=False):
    import socket

    if not all([host, port]):
        log.error('Please specify host and port')
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((host, port))
    if result == 0:
        if debug:
            log.info('Port {} is open'.format(port))
        return True
    else:
        if debug:
            log.info('Port {} is not open'.format(port))
        return False
