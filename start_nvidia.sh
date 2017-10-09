#!/bin/sh

ROOT_DIR=$1

cd ROOT_DIR

tmux new -d -s api "python3 api/api.py --api --gpu-type nvidia --getdata-interval 10"
tmux new -d -s oc  "python3 nvset.py -c oc.ini -D"
