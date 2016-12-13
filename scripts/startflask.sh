#!/bin/sh

export PYTHONPATH=${PYTHONPATH-}:$CHARM_DIR/lib
export FLASK_APP=./lib/CIGWServer.py;
flask run -h 0.0.0.0
