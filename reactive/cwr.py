import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from utils import (
    REST_PORT,
    REST_PREFIX,
    CONTROLLERS_LIST_FILE,
    get_controllers,
    get_charmstore_token,
    report_status
)
from charmhelpers import fetch
from charmhelpers.core import host, hookenv
from charms.reactive import (
    hook,
    when,
    when_not,
    set_state,
    remove_state,
    is_state,
    when_file_changed,
    RelationBase
)
from jujubigdata import utils
from jenkins import Jenkins
from CIGateway import CIGateway


def pip_install_from_git(version, wheelhouse, repo):
    with TemporaryDirectory() as tmpdir:
        utils.run_as('root', 'git', 'clone', repo, tmpdir)
        install_cmd = ['root', 'pip%s' % version, 'install', tmpdir]
        if wheelhouse:
            install_cmd.extend(
                ['--no-index', '-f', os.path.join(tmpdir, 'wheelhouse')])
        utils.run_as(*install_cmd)


@when_not('juju-ci-env.installed')
def install_juju():
    hookenv.status_set('maintenance', 'Installing juju.')
    fetch.add_source("ppa:juju/stable")
    fetch.apt_update()
    fetch.apt_install(["juju", "charm-tools"])
    # bt/cwr are not py3 compatible yet (hence not in the wheelhouse)
    utils.run_as('root', 'pip2', 'install', 'bundletester')
    # cwr on pypi is out of date :(
    pip_install_from_git(
        2, False, 'https://github.com/juju-solutions/cloud-weather-report')
    # matrix not released to pypi yet
    pip_install_from_git(
        3, True, 'https://github.com/juju-solutions/matrix')
    # juju plugins (for crashdump). Skip if already deployed.
    plugins_dir = '/usr/local/lib/juju-plugins'
    if not os.path.isdir(plugins_dir):
        utils.run_as('root', 'git', 'clone', 'https://github.com/juju/plugins',
                     plugins_dir)
    else:
        with host.chdir(plugins_dir):
            utils.run_as('root', 'git', 'pull', 'origin', 'master')

    for plugin in Path(plugins_dir).iterdir():
        if plugin.name.startswith('juju-'):
            target_file = Path('/usr/local/bin/{}'.format(plugin.name))
            if not target_file.is_file():
                target_file.symlink_to(plugin)

    # Make user jenkins parametrised. And this action as well
    with open("/etc/sudoers", "a") as sudoers:
        sudoers.write("%jenkins ALL=NOPASSWD: ALL\n")

    host.chownr("/srv/artifacts",
                owner="jenkins",
                group="jenkins",
                chowntopdir=True)

    set_state('juju-ci-env.installed')
    report_status()


@when('jenkins.available', 'juju-ci-env.installed')
@when_not('jenkins.jobs.ready')
def install_jenkins_jobs(connected_jenkins):
    hookenv.status_set('maintenance', 'Uploading jenkins jobs.')
    jenkins_connection_info = connected_jenkins.get_connection_info()
    jclient = Jenkins(jenkins_connection_info["jenkins_url"],
                      jenkins_connection_info["admin_username"],
                      jenkins_connection_info["admin_password"])

    for dirname, dirnames, _ in os.walk('jobs'):
        for subdirname in dirnames:
            if jclient.job_exists(subdirname):
                jclient.delete_job(subdirname)
            jobfilename = os.path.join(dirname, subdirname, "config.xml")
            with open(jobfilename, 'r') as jobfile:
                configxml = jobfile.read()
                jclient.create_job(subdirname, configxml)

    plugins = ["github", "ghprb", "postbuildscript", "scripttrigger"]
    for plugin in plugins:
        hookenv.status_set('maintenance', 'Installing plugin {}.'
                           .format(plugin))
        reboot = jclient.install_plugin(plugin)
        hookenv.log("Installing plugin {}. Restart required: {}"
                    .format(plugin, reboot))
        installed = wait_for_plugin(plugin)
        if not installed:
            hookenv.log("installation of {} did not complete on time."
                        .format(plugin))

    # Give some slack for syncing the plugins.
    time.sleep(15)
    host.service_restart("jenkins")

    CIGateway.start(jenkins_connection_info["jenkins_url"],
                    jenkins_connection_info["admin_username"],
                    jenkins_connection_info["admin_password"])
    set_state("jenkins.jobs.ready")
    hookenv.open_port(REST_PORT)
    report_status()


@when('jenkins.jobs.ready')
@when_not('jenkins.available')
def cleanup_jenkins():
    '''
    Try to remove the jenkins jobs setup during initialisation,
    and stop the CI gateway service.
    '''
    hookenv.status_set('maintenance', 'Deleting jenkins jobs.')

    CIGateway.stop()
    hookenv.close_port(REST_PORT)

    # Since Jenkins is no more available. Ask the CIGateway to provide
    # a jenkins client (and hope Jenkins is still there)
    # but we do not want to block the deployment either way
    try:
        jclient = CIGateway.get_current_jenkins()

        for _, dirnames, _ in os.walk('jobs'):
            for subdirname in dirnames:
                jclient.delete_job(subdirname)
    except Exception as err:
        hookenv.log("Got an exception while cleaning up.")
        hookenv.log(err)

    remove_state("jenkins.jobs.ready")
    report_status()


@when('ci-client.joined')
def client_joined(client):
    inform_client(client)
    report_status()


@when_not('jenkins.available')
def jenkins_unavailable():
    if is_state('ci-client.joined'):
        ci_client = RelationBase.from_state('ci-client.joined')
        inform_client(ci_client)
    report_status()


@when('jenkins.available', 'jenkins.has.changed')
def ci_connection_updated(jenkins, jenkins_changed):
    jenkins_connection_info = jenkins.get_connection_info()
    hookenv.status_set('maintenance', 'Configuring CI gateway.')
    CIGateway.stop()
    CIGateway.start(jenkins_connection_info["jenkins_url"],
                    jenkins_connection_info["admin_username"],
                    jenkins_connection_info["admin_password"])
    jenkins.change_acked()
    report_status()


@when_file_changed(CONTROLLERS_LIST_FILE)
def controllers_updated():
    hookenv.log("Controllers file has changed")
    if is_state('ci-client.joined'):
        hookenv.log("Contacting clients")
        ci_client = RelationBase.from_state('ci-client.joined')
        inform_client(ci_client)
    report_status()


@when('jenkins.available')
def jenkins_available(jenkins):
    report_status()


@hook('upgrade-charm')
def restart_ciserver():
    if is_state("jenkins.jobs.ready"):
        CIGateway.restart()


def inform_client(client):
    controllers = get_controllers()
    token = get_charmstore_token()
    if len(controllers) == 0 or not is_state('jenkins.available'):
        client.clear_ready()
    else:
        client.set_controllers(controllers)
        client.set_port(REST_PORT)
        client.set_rest_prefix(REST_PREFIX)
        client.set_store_token(token)  # token may be empty; client will verify
        client.set_ready()


def wait_for_plugin(plugin, wait_for_secs=300):
    '''
    Waits for 5 minutes to see if the plugin is available.
    Args:
        plugin: the plugin to look for
        wait_for_secs: how long should we wait for the plugin to appear

    Returns: True if the plugin got deployed

    '''
    timeout = time.time() + wait_for_secs
    while True:
        if time.time() > timeout:
            return False
        all_plugins = os.listdir("/var/lib/jenkins/plugins")
        if "{}.hpi".format(plugin) in all_plugins:
            return True
        if "{}.jpi".format(plugin) in all_plugins:
            return True
        time.sleep(15)
