#!/bin/sh

ROOT_DIR=$1
tmux new -d -s api "python3 $ROOT_DIR/api/api.py --api --gpu-type nvidia --getdata-interval 10"
tmux new -d -s oc  "python3 $ROOT_DIR/nvset.py -c oc.ini -D"
