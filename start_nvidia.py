import os
import sys
import logging as log


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_LEVEL = log.DEBUG
log.basicConfig(format='[%(levelname)s] %(message)s', level=LOG_LEVEL)


api_fp = os.path.join(ROOT_DIR, 'api', 'api.py')
oc_fp = os.path.join(ROOT_DIR, 'nvset.py')
miner_fp = os.path.join(ROOT_DIR, 'miner.py')
ini_fp = os.path.join(ROOT_DIR, 'oc.ini')

path_list =(
    api_fp,
    oc_fp,
    ini_fp
)


def check_fp(l):
    for i in l:
        if os.path.exists(i):
            log.info('{} [exists]'.format(i))
        else:
            log.error('{} [not found]'.format(i))
            sys.exit(1)

check_fp(path_list)


os.system('tmux new -d -s api \"python3 {} --api --gpu-type nvidia --getdata-interval 10\"'.format(api_fp))
os.system('tmux new -d -s oc  \"python3 {} -c {} -D\"'.format(oc_fp, ini_fp))
os.system('tmux new -d -s watchdog python3 {} --minimal-hashrate 305 --debug --miner-api-port 3333'.format(miner_fp))
