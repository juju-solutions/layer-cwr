#!/usr/bin/env python3

import sys
import time
import yaml

sys.path.append('lib')
from charms.layer.basic import activate_venv  # noqa: E402
activate_venv()

from charmhelpers.core import hookenv  # noqa: E402
from jenkins import NotFoundException  # noqa: E402
from theblues.charmstore import CharmStore  # noqa: E402
from theblues.errors import EntityNotFound, ServerError  # noqa: E402


def app_from_bundle(bundle_name, charm_name):
    '''Return the app name used in the given bundle for a given charm.'''
    cs = CharmStore()
    bundle_yaml = cs.files(bundle_name, filename='bundle.yaml', read_file=True)
    yaml_contents = yaml.safe_load(bundle_yaml)
    for app, app_config in yaml_contents['services'].items():
        if charm_name in app_config['charm']:
            return app
    return None


def fetch_reference_bundle(charm_name):
    try:
        tests_yaml = CharmStore().files(charm_name,
                                        filename='tests/tests.yaml',
                                        read_file=True)
        tests_yaml = yaml.safe_load(tests_yaml)
        return tests_yaml.get('reference-bundle')
    except EntityNotFound:
        return None  # probably doesn't have a test.yaml
    except (ServerError, yaml.YAMLError) as e:
        hookenv.log('Unable to load test.yaml from %s: %s' % (
            charm_name, e), hookenv.ERROR)


def get_reference_bundle():
    # If we have a reference bundle, determine the app name used for our charm
    charm_name = hookenv.action_get("charm-name")
    if hookenv.action_get("reference-bundle"):
        bundle_name = hookenv.action_get("reference-bundle")
    else:
        # try to get the reference bundle from tests.yaml
        bundle_name = fetch_reference_bundle(charm_name)

    if bundle_name:
        if bundle_name.startswith('bundle:'):
            # normalize bundle: style URL (why do we even accept this?)
            bundle_name = 'cs:' + bundle_name[7:]
        elif not bundle_name.startswith('cs:'):
            bundle_name = 'cs:' + bundle_name
        bundle_app_name = app_from_bundle(bundle_name, charm_name)

        if not bundle_app_name:
            fail_action("{} not found in {}".format(charm_name, bundle_name))
        return bundle_name, bundle_app_name
    else:
        return "", ""


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
