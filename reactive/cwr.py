import os
import time
from charmhelpers import fetch
from charmhelpers.core import host, hookenv
from charms.reactive import (
    when,
    when_not,
    set_state,
    is_state,
    when_file_changed,
    RelationBase
)
from jujubigdata import utils
from jenkins import Jenkins
from CIGateway import CIGateway
from controller import helpers


@when_not('juju-ci-env.installed')
def install_juju():
    hookenv.status_set('maintenance', 'installing juju')
    fetch.add_source("ppa:juju/stable")
    fetch.apt_update()
    fetch.apt_install(["juju", "zfsutils-linux", "charm-tools",
                       "unzip", "expect"])

    utils.run_as('root', 'lxd', 'init', '--auto')
    utils.run_as('root', 'scripts/lxd-reconf.sh')

    # Make user jenkins parametrised. And this action as well
    with open("/etc/sudoers", "a") as sudoers:
        sudoers.write("%jenkins ALL=NOPASSWD: ALL\n")
    utils.run_as('root', 'usermod', '-a', '-G', 'lxd', 'jenkins')
    utils.run_as('root', 'pip', 'install', '--upgrade', 'pip')
    utils.run_as('root', 'python', '-m',
                 'pip', 'install', 'bundletester')
    utils.run_as('root', 'python', '-m',
                 'pip', 'install', 'cloud-weather-report')
    utils.run_as('root', 'pip', 'install', '--upgrade', 'flask')
    utils.run_as('root', 'pip', 'install', '--upgrade', 'python-jenkins')

    set_state('juju-ci-env.installed')
    report_status()


@when('jenkins.available', 'juju-ci-env.installed')
@when_not('jenkins.jobs.ready')
def install_jenkins_jobs(connected_jenkins):
    hookenv.status_set('maintenance', 'uploading jenkins jobs')
    jenkins_connection_info = connected_jenkins.get_connection_info()
    jclient = Jenkins(jenkins_connection_info["jenkins_url"],
                      jenkins_connection_info["admin_username"],
                      jenkins_connection_info["admin_password"])

    for dirname, dirnames, _ in os.walk('jobs'):
        for subdirname in dirnames:
            jobfilename = os.path.join(dirname, subdirname, "config.xml")
            with open(jobfilename, 'r') as jobfile:
                configxml = jobfile.read()
                jclient.create_job(subdirname, configxml)

    plugins = ["github", "ghprb", "postbuildscript"]
    for plugin in plugins:
        hookenv.status_set('maintenance', 'Installing plugin {}'
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
    report_status()


@when('ci-client.joined')
def client_joined(client):
    inform_client(client)


@when_not('jenkins.available')
def jenkins_unavailable():
    if is_state('ci-client.joined'):
        ci_client = RelationBase.from_state('ci-client.joined')
        inform_client(ci_client)
    report_status()


@when('jenkins.available', 'jenkins.has.changed')
def ci_connection_updated(jenkins, jenkins_changed):
    jenkins_connection_info = jenkins.get_connection_info()
    hookenv.status_set('maintenance', 'configuring CI gateway.')
    CIGateway.stop()
    CIGateway.start(jenkins_connection_info["jenkins_url"],
                    jenkins_connection_info["admin_username"],
                    jenkins_connection_info["admin_password"])
    jenkins.change_acked()
    report_status()


def report_status():
    if not is_state('jenkins.available'):
        hookenv.status_set('waiting', 'waiting for jenkins to become available')
        return

    # jenkins.available is set from here on
    if not is_state('jenkins.jobs.ready'):
        hookenv.status_set('waiting', 'waiting jobs to be uploaded to jenkins')
        return

    # jenkins.available and jenkins.jobs.ready are set from here on
    controllers = helpers.get_controllers()
    if len(controllers) == 0:
        hookenv.status_set('blocked', 'waiting for controller registration')
        return

    # jenkins.available and jenkins.jobs.ready and controllers > 0 from here on
    hookenv.status_set('active', 'ready')


@when_file_changed(helpers.CONTROLLERS_LIST_FILE)
def controllers_updated():
    hookenv.log("Contorllers file has changed")
    if is_state('ci-client.joined'):
        hookenv.log("Contacting clients")
        ci_client = RelationBase.from_state('ci-client.joined')
        inform_client(ci_client)
    report_status()


def inform_client(client):
    controllers = helpers.get_controllers()
    if len(controllers) == 0 or not is_state('jenkins.available'):
        client.clear_ready()
    else:
        client.set_ready(5000, controllers)


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
        if "{}.jpi".format(plugin) in all_plugins:
            return True
        time.sleep(15)
