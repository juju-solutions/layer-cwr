#!/usr/bin/env python3

import errno
import os
import shutil
import subprocess
import sys
import time
import yaml

sys.path.append('lib')
from charms.layer.basic import activate_venv  # noqa: E402
activate_venv()

from jenkins import Jenkins, JenkinsException  # noqa: E402

from charmhelpers.core import hookenv  # noqa: E402
from charmhelpers.core import templating  # noqa: E402
from charms.reactive import RelationBase  # noqa: E402
from jenkins import NotFoundException  # noqa: E402
from theblues.charmstore import CharmStore  # noqa: E402
from theblues.errors import EntityNotFound, ServerError  # noqa: E402
from utils import (
    get_badge_path,
    get_hook_token,
    get_fname,
    get_output_scenarios,
    get_rest_path,
    REST_PORT,
)  # noqa: E402


# if you update this path, make sure to update the same path in cwr-helpers.sh
HOME = "/var/lib/jenkins"
CONFIG_DIR = 'configuration'
CONTAINER_HOME = "/root"


class InvalidBundle(Exception):
    def __init__(self, name, reason):
        self.name = name
        self.reason = reason

    def __str__(self):
        return 'Invalid bundle: {}'.format(self.name)


def app_from_bundle(bundle_name, charm_name):
    '''Return the app name used in the given bundle for a given charm.'''
    try:
        cs = CharmStore()
        bundle_yaml = cs.files(bundle_name,
                               filename='bundle.yaml',
                               read_file=True)
        yaml_contents = yaml.safe_load(bundle_yaml)
    except (EntityNotFound, ServerError, yaml.YAMLError) as e:
        raise InvalidBundle(bundle_name, str(e))
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


def get_charm_names():
    '''
    Returns the given charm name and a sanitized version that matches
    CWR artifact naming.
    '''
    charm_name = hookenv.action_get("charm-name")
    charm_fname = get_fname(charm_name)
    return charm_name, charm_fname


def _get_reference_bundle():
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
            raise InvalidBundle(
                bundle_name,
                "Charm not found in bundle: {}".format(charm_name))
        bundle_fname = get_fname(bundle_name)
        return bundle_name, bundle_fname, bundle_app_name
    else:
        return "", "", ""


def get_reference_bundle():
    try:
        bundle_name, bundle_fname, bundle_app_name = _get_reference_bundle()
    except InvalidBundle as e:
        fail_action(str(e), e.reason)
    if not bundle_name:
        fail_action('Charm does not provide reference bundle and none was '
                    'provided to action')
    return bundle_name, bundle_fname, bundle_app_name


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


def get_s3_credentials(cred_name=None):
    """Get S3 credentials from the juju credentials command.

    if cred_name is set, get the credentials for the name.
    if cred_name is not set, try to get the credentials for the default name.
    if cred_name is not set, no default credential name and there is a single
      credential name, get the credentials for that name.

    Returns: access_key, secret_key
    """
    cmd = ('sudo -H -u jenkins -- juju credentials aws --format yaml '
           '--show-secrets'.split())
    try:
        creds = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        fail_action(
            "Error running 'juju credentials' command: ".format(e.output))
    creds = yaml.load(creds)
    if not creds.get('credentials', {}).get('aws'):
        fail_action('AWS credentials not found. Set AWS credentials by '
                    'running "set-credentials" action.')
    if not cred_name:
        cred_name = creds.get('credentials', {}).get('aws', {}).get(
            'default-credential')
    if (not cred_name and
            len(creds.get('credentials', {}).get('aws', {}).keys()) == 1):
        cred_name = list(creds.get('credentials', {}).get('aws', {}).keys())[0]
    if not cred_name:
        fail_action('Credentials not found. Set AWS credentials by '
                    'running "set-credentials" action.')
    access_key = creds['credentials']['aws'][cred_name]['access-key']
    secret_key = creds['credentials']['aws'][cred_name]['secret-key']
    return access_key, secret_key


def create_s3_config_file(filename, access_key, secret_key):
    """Create S3 config file containing access and secret keys."""
    ensure_dir(os.path.dirname(filename))
    with open(filename, 'w') as f:
        f.write('[default]\n')
        f.write('access_key = {}\n'.format(access_key))
        f.write('secret_key = {}\n'.format(secret_key))
    shutil.chown(filename, 'jenkins', 'jenkins')


def ensure_dir(dirpath):
    """Creates directories for dir path if they don't already exist."""
    try:
        os.makedirs(dirpath)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def get_s3_options(s3_config_filepath, s3_container_filepath):
    """Generate CWR options to store the test results to S3 storage."""
    bucket = hookenv.action_get("bucket")
    if not bucket:
        return ''
    results_dir = hookenv.action_get("results-dir")
    if not results_dir:
        fail_action('"results-dir" must be provided if "bucket" name is set.')
    private = hookenv.action_get("private") or False
    cred_name = hookenv.action_get("credential-name")
    access_key, secret_key = get_s3_credentials(cred_name)
    create_s3_config_file(s3_config_filepath, access_key, secret_key)
    private_opt = ""
    if private:
        private_opt = " --s3-private"
    s3_opt = '--bucket {} --results-dir {} --s3-creds {}{}'.format(
        bucket, results_dir, s3_container_filepath, private_opt)
    return s3_opt


def get_s3_creds_filenames(job_name):
    s3_creds = "{}.s3cfg".format(os.path.join(HOME, CONFIG_DIR, job_name))
    s3_creds_container = os.path.join(
        CONTAINER_HOME, CONFIG_DIR, os.path.basename(s3_creds))
    return s3_creds, s3_creds_container


def make_jenkins_client():
    jenkins_relation = (RelationBase.from_state('jenkins.available'))
    jenkins_connection_info = jenkins_relation.get_connection_info()
    return Jenkins(jenkins_connection_info["jenkins_url"],
                   jenkins_connection_info["admin_username"],
                   jenkins_connection_info["admin_password"])


def get_common_context(job_name, charm_name, bundle_name, app_name_in_bundle):
    """Return dict containing the values to be replaced in the template."""
    s3_creds, s3_creds_container = get_s3_creds_filenames(job_name)
    s3_options = get_s3_options(s3_creds, s3_creds_container)
    context = {
        "gitrepo": hookenv.action_get("repo"),
        "charm_subdir": hookenv.action_get("charm-subdir"),
        "pushtochannel": hookenv.action_get("push-to-channel") or "",
        "lp_id": hookenv.action_get("namespace"),
        "charm_name": charm_name,
        "bundle_name": bundle_name,
        "app_name_in_bundle": app_name_in_bundle,
        "series": hookenv.action_get("series") or "",
        "controller": hookenv.action_get("controller") or "",
        "job_name": job_name,
        "output_scenarios": get_output_scenarios(),
        "s3_options": s3_options,
    }
    return context


def create_jenkins_job(jenkins_client, source, context, job_name, target=None):
    """Create Jenkins job and return hook token.

    Args:
        jenkins_client: Jenkins client
        source: Source template
        context: dict containing the values to be replaced in the template.
        job_name:  Jenkins job name
        target: Target file path. If none, no file will be written.

    Returns:
        Hook token.
    """
    job_contents = templating.render(
        source=source, target=target, context=context)
    try:
        jenkins_client.create_job(job_name, job_contents)
    except JenkinsException as e:
        fail_action(str(e))
    token = get_hook_token(job_name)
    return token


def get_info_urls(trigger_path, token, job_name):
    url = "http://<cwr-ip>:{}{}/{}/{}/{}".format(
        REST_PORT, get_rest_path(), trigger_path, job_name, token)
    badge_url = "http://<cwr-ip>:{}{}".format(
        REST_PORT, get_badge_path(job_name))
    return url, badge_url
