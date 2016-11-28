from charmhelpers import fetch
from charmhelpers.core import host, hookenv
from charms.reactive import when, when_not, set_state, remove_state
from jujubigdata import utils

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

    utils.run_as('jenkins', 'cp', '-r', 'jobs', '/var/lib/jenkins')
    set_state('juju-ci-env.installed')
    hookenv.status_set('active', 'Ready')

