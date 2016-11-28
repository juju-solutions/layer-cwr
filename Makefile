#!/usr/bin/make
PYTHON := /usr/bin/env python

all: lint test


lint:
	@flake8 --exclude hooks/charmhelpers hooks tests
	@charm proof

test:
	@echo Starting Amulet tests...
	# coreycb note: The -v should only be temporary until Amulet sends
	# raise_status() messages to stderr:
	#   https://bugs.launchpad.net/amulet/+bug/1320357
	@juju test -v -p AMULET_HTTP_PROXY,AMULET_OS_VIP --timeout 2700
