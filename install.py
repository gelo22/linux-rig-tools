#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys

def parse_args():
    '''Parse configuration from config and cmd'''
    # parse args
    parser = argparse.ArgumentParser()
    parser.add_argument('--miner_name', default='ccminer', help='miner name which will be installed')
    args = parser.parse_args()
    # init config dictionary
    conf = dict()
    # add parsed args to config dictionary
    for key in vars(args):
        if vars(args)[key]:
            conf[key] = vars(args)[key]
    # add base dir
    conf['base_dir'] = os.path.dirname(os.path.abspath(__file__))
    # add miners repos
    conf['miners_repos'] = {'ccminer': 'https://github.com/tpruvot/ccminer.git'}
    return conf

def _subprocess(cmd):
    '''Shortcut for subprocess generic code'''
    my_stdout = sys.stdout
    my_stderr = sys.stderr
    print('\nCommand: {0}'.format(' '.join(cmd)))
    proc = subprocess.Popen(cmd, stdout=my_stdout, stderr=my_stderr)
    returncode = proc.wait()
    if returncode != 0:
        print('Return code of "{0}" is: {1}'.format(' '.join(cmd), returncode))

def _customize_ccminer_makefile():
    '''Customize makefile'''
    makefile_tmp = list()
    # make tmp file
    makefile_name = '{0}/build/ccminer/Makefile.am'.format(conf['base_dir'])
    with open(makefile_name) as makefile_obj:
        for line in makefile_obj:
            if line.startswith('nvcc_ARCH'):
                line = 'nvcc_ARCH  = -gencode=arch=compute_61,code=\\"sm_61,compute_61\\"\n'
            makefile_tmp.append(line)
    # write new file
    with open(makefile_name, 'w') as makefile_obj:
        for line in makefile_tmp:
            makefile_obj.write(line)
    
def prepare_miner_build(miner_name):
    '''All operations before build'''
    print('Prepearing miner build')
    commands = ['apt-get -y update',
                'dpkg-reconfigure debconf -f noninteractive',
                'apt-get -y install software-properties-common git gcc-5 g++-5',
                'update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-5 1',
                'add-apt-repository -y ppa:graphics-drivers/ppa',
                'apt-get -y update',
                'apt-get install -y nvidia-384-dev nvidia-384 nvidia-cuda-toolkit',
                'apt-get install -y libcurl4-openssl-dev libssl-dev libjansson-dev automake autotools-dev build-essential'
               ]
    for tmp_cmd in commands:
        cmd = 'sudo -n {0}'.format(tmp_cmd).split()
        _subprocess(cmd)

    os.chdir(conf['base_dir'])
    if not os.path.isdir('build'):
        os.mkdir('build')
    if not os.path.isdir('build/' + miner_name):
        _subprocess('git clone {0} build/{1}'.format(conf['miners_repos'][miner_name], miner_name).split())

    if miner_name == 'ccminer':
        _customize_ccminer_makefile()

def build_miner(miner_name):
    '''Run miner build'''
    print('Miner building started')
    os.chdir('build/' + miner_name)
    _subprocess(['./build.sh'])

if __name__ == '__main__':
    conf = parse_args()
    prepare_miner_build(conf['miner_name'])
    _customize_ccminer_makefile()
    build_miner(conf['miner_name'])

