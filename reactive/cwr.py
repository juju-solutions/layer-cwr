import os
import time
from charmhelpers import fetch
from charmhelpers.core import host, hookenv
from charms.reactive import when, when_not, set_state
from jujubigdata import utils
from jenkins import Jenkins
from CIGateway import CIGateway


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
    hookenv.status_set('active', 'Ready')


@when('jenkins.available')
@when_not('jenkins.jobs.ready')
def install_jenkins_jobs(connected_jenkins):
    hookenv.status_set('maintenance', 'Uploading Jenkins jobs')
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
    hookenv.status_set('active', 'Ready')
    set_state("jenkins.jobs.ready")


@when('ci-client.joined')
def client_joined(client):
    client.set_ready(5000)


@when('jenkins.available', 'jenkins.has.changed')
def ci_connection_updated(jenkins, jenkins_changed):
    jenkins_connection_info = jenkins.get_connection_info()
    hookenv.status_set('maintenance', 'Configuring CI gateway.')
    CIGateway.stop()
    CIGateway.start(jenkins_connection_info["jenkins_url"],
                    jenkins_connection_info["admin_username"],
                    jenkins_connection_info["admin_password"])
    jenkins.change_acked()
    hookenv.status_set('active', 'Ready')


def wait_for_plugin(plugin, wait_for=300):
    '''
    Waits for 5 minutes to see if the plugin is available.
    Args:
        plugin: the plugin to look for

    Returns: True if the plugin got deployed

    '''
    timeout = time.time() + wait_for
    while True:
        if time.time() > timeout:
            return False
        all_plugins = os.listdir("/var/lib/jenkins/plugins")
        if "{}.jpi".format(plugin) in all_plugins:
            return True
        time.sleep(15)
