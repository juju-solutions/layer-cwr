import re
import time
import base64
import os
import yaml
import uuid
from charmhelpers.core import hookenv
from charms.reactive import is_state

TRIGGER_PERIODICALLY = '''
    <hudson.triggers.SCMTrigger>
      <spec>*/5 * * * *</spec>
      <ignorePostCommitHooks>false</ignorePostCommitHooks>
    </hudson.triggers.SCMTrigger>
    '''

SKIP_BUILDS = '''
if [ ! -f "first-run.lock" ]; then
  touch "first-run.lock"
  echo "First run automatically triggered. Skipped."
  touch results.xml
  exit 0
fi

if test `find "first-run.lock" -mmin -1`
then
  echo "Skip build. Caused by tag already present in repo."
  touch results.xml
  exit 0
fi
'''

REFSPEC = "<refspec>+refs/tags/*:refs/remotes/origin/tags/*</refspec>"

HOOK_TOKENS_LIST_FILE = "/var/lib/jenkins/tokens.yaml"
CONTROLLERS_LIST_FILE = "/var/lib/jenkins/controller.names"
REST_PORT = 5000
REST_PREFIX = "ci"
REST_VER = "v1.0"


def get_fname(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)


def trigger_jenkins_job(jclient, job, attempts=5):
    params = {'BUILD_TAG': ""}
    name = jclient.get_job_name(job)
    attempt = 1
    while name is None and attempt < attempts:
        time.sleep(10)
        name = jclient.get_job_name(job)
    jclient.build_job(job, params)


def get_hook_token(job_name):
    tokens = {}
    try:
        with open(HOOK_TOKENS_LIST_FILE, "r+") as fp:
            tokens = yaml.load(fp)
    except IOError:
        print("Tokens file will be created")

    if job_name not in tokens:
        tokens[job_name] = str(uuid.uuid4())
        with open(HOOK_TOKENS_LIST_FILE, "w") as fp:
            yaml.dump(tokens, fp)

    return tokens[job_name]


def validate_hook_token(job_name, token):
    tokens = {}
    try:
        with open(HOOK_TOKENS_LIST_FILE, "r") as fp:
            tokens = yaml.load(fp)
    except IOError:
        print("Tokens file not created yet")

    if job_name not in tokens:
        return False
    return tokens[job_name] == token


def get_charmstore_token(decode=True):
    """
    Read the charm store usso token from disk.

    The charm store token will be written to disk by the 'store-login' action.
    If present, return the contents of the token file as a base64 encoded
    string. If decode=False, return this as a bytes array.
    """
    token_path = "/var/lib/jenkins/.local/share/juju/store-usso-token"
    token = ""
    if os.path.exists(token_path):
        with open(token_path, 'r') as f:
            token = base64.b64encode(f.read().encode('utf-8'))
        if decode:
            token = token.decode('utf-8')
    return token


def get_controllers():
    controllers_file = CONTROLLERS_LIST_FILE
    controllers = []
    if os.path.exists(controllers_file):
        controllers = [line.rstrip('\n') for line in open(controllers_file)]

    return controllers


def get_rest_path():
    """Return the 'path' portion of the REST URL."""
    return "/" + REST_PREFIX + "/" + REST_VER


def get_badge_path(job):
    """The path to a jobs build badge."""
    return "/{}/build-badge.svg".format(job)


def report_status():
    if not is_state('jenkins.available'):
        hookenv.status_set('waiting',
                           'Waiting for jenkins to become available.')
        return

    # jenkins.available is set from here on
    if not is_state('jenkins.jobs.ready'):
        hookenv.status_set('waiting',
                           'Waiting for jenkins jobs to be uploaded.')
        return

    # jenkins.available and jenkins.jobs.ready are set from here on
    controllers = get_controllers()
    if len(controllers) == 0:
        hookenv.status_set('blocked',
                           'Waiting for controller registration.')
        return

    # jenkins.available and jenkins.jobs.ready and controllers > 0 from here on
    if get_charmstore_token():
        msg = ('Ready (controllers: {}; store: authenticated).'
               .format(controllers))
    else:
        msg = ('Ready (controllers: {}; store: unauthenticated).'
               .format(controllers))
    hookenv.status_set('active', msg)
