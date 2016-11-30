import os
import time
from charmhelpers import fetch
from charmhelpers.core import host, hookenv
from charms.reactive import when, when_not, set_state, remove_state
from jujubigdata import utils
from jenkins import Jenkins, JenkinsException


@when_not('juju-ci-env.installed')
def install_juju():
    hookenv.status_set('maintenance', 'installing juju')
    fetch.add_source("ppa:juju/stable")
    fetch.apt_update()
    fetch.apt_install(["juju", "zfsutils-linux", "charm-tools", "unzip", "expect"])

    utils.run_as('root', 'lxd', 'init', '--auto')
    utils.run_as('root', 'scripts/lxd-reconf.sh')

    # Make user jenkins parametrised. And this action as well
    with open("/etc/sudoers", "a") as sudoers:
        sudoers.write("%jenkins ALL=NOPASSWD: ALL\n")
    utils.run_as('root', 'usermod', '-a', '-G', 'lxd', 'jenkins')
    utils.run_as('root', 'pip', 'install', '--upgrade', 'pip')
    utils.run_as('root', 'python', '-m', 'pip', 'install', 'bundletester')
    utils.run_as('root', 'python', '-m', 'pip', 'install', 'cloud-weather-report')

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
        hookenv.status_set('maintenance', 'Installing plugin {}'.format(plugin))
        reboot = jclient.install_plugin(plugin)
        hookenv.log("Installing plugin {}. Restart required: {}".format(plugin, reboot))
        installed = wait_for_plugin(plugin)
        if not installed:
            hookenv.log("installation of {} did not complete after 5 minutes.".format(plugin))

    # Give some slack for syncing the plugins.
    time.sleep(15)
    host.service_restart("jenkins")

    hookenv.status_set('active', 'Ready')
    set_state("jenkins.jobs.ready")


def wait_for_plugin(plugin):
    '''
    Waits for 5 minutes to see if the plugin is available.
    Args:
        plugin: the plugin to look for

    Returns: True if the plugin got deployed

    '''
    timeout = time.time() + 300
    while True:
        if time.time() > timeout:
            return False
        allplugins = os.listdir("/var/lib/jenkins/plugins")
        if "{}.jpi".format(plugin) in allplugins:
            return True
        time.sleep(15)
