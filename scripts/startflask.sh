#!/bin/sh

# script is executed from $CHARM_DIR; set relative paths accordingly
export PATH=../.venv/bin:$PATH
export PYTHONPATH=${PYTHONPATH-}:./lib
export FLASK_APP=./lib/CIGWServer.py;
flask run -h 0.0.0.0
