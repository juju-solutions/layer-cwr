#!/usr/bin/env python3

import sys
import time
import yaml

sys.path.append('lib')
from charms.layer.basic import activate_venv  # noqa: E402
activate_venv()

from charmhelpers.core import hookenv  # noqa: E402
from jenkins import NotFoundException  # noqa: E402
from theblues import charmstore  # noqa: E402


def app_from_bundle(bundle, charm):
    '''Return the app name used in the given bundle for a given charm.'''
    cs = charmstore.CharmStore()
    bundle_yaml = cs.files(bundle, filename='bundle.yaml', read_file=True)
    yaml_contents = yaml.safe_load(bundle_yaml)
    for app, app_config in yaml_contents['services'].items():
        if charm in app_config['charm']:
            return app
    return None


def fail_action(msg, output=None):
    '''Fail an action with a message and (optionally) additional output.'''
    if output:
        hookenv.action_set({'output': output})
    hookenv.action_fail(msg)
    sys.exit()


def wait_result(jclient, job_name, build_number, secs_to_wait=60):
    timeout = time.time() + secs_to_wait
    while True:
        time.sleep(5)
        if time.time() > timeout:
            raise Exception("Job timeout")
        try:
            build_info = jclient.get_build_info(job_name, build_number)
            if build_info["result"] == 'FAILURE':
                outcome = 'fail'
            else:
                outcome = 'success'

            output = jclient.get_build_console_output(job_name, build_number)
            return outcome, output
        except NotFoundException:
            print("Jenkins job {} not running yet".format(build_number))
        except:
            raise
