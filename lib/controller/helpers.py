import base64
import os


CONTROLLERS_LIST_FILE = "/var/lib/jenkins/controller.names"
REST_PORT = 5000
REST_PREFIX = "ci"
REST_VER = "v1.0"


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
