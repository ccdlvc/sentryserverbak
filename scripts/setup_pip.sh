#!/usr/bin/env bash
curl "https://bootstrap.pypa.io/get-pip.py" -o "get-pip.py"
python get-pip.py

export CFLAGS=-Qunused-arguments
export CPPFLAGS=-Qunused-arguments
sudo -E pip install psycopg2