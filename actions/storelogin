#!/usr/bin/env python3
import os
import errno
import base64
import subprocess
from charmhelpers.core.host import chownr


def charmstore_login():
    """Login to the charmstore.
    As long as we have an oauth token (which will be passed in via config),
    `charm login` should be non-interactive, creating/refreshing ~/.go-cookies
    as necessary. (shamelessly stolen from review-queue!)
    """
    token_path = '/var/lib/jenkins/.local/share/juju/store-usso-token'
    if not os.path.exists(token_path):
        token_value = hookenv.action_get('charmstoretoken')
        if not token_value:
            raise ValueError('Missing USSO token')
        if not os.path.isdir(os.path.dirname(token_path)):
            try:
                os.makedirs(os.path.dirname(token_path))
            except OSError as e:
                if e.errno == errno.EEXIST:
                    pass
                else:
                    raise
        with open(token_path, 'w') as f:
            f.write(base64.b64decode(token_value))
        os.chmod(token_path, 0o600)
    chownr('/var/lib/jenkins/.local', chowntopdir=True)
    cmd = ['su', 'jenkins', '-c', 'charm login']
    if subprocess.call(cmd) != 0:
        raise Exception


if __name__ == "__main__":
    charmstore_login()
