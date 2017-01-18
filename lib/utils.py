from controller import helpers
from charmhelpers.core import hookenv
from charms.reactive import is_state


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
    controllers = helpers.get_controllers()
    if len(controllers) == 0:
        hookenv.status_set('blocked',
                           'Waiting for controller registration.')
        return

    # jenkins.available and jenkins.jobs.ready and controllers > 0 from here on
    if helpers.get_charmstore_token():
        msg = ('Ready (controllers: {}; store: authenticated).'
               .format(controllers))
    else:
        msg = ('Ready (controllers: {}; store: unauthenticated).'
               .format(controllers))
    hookenv.status_set('active', msg)
