import os
import pwd
from pathlib import Path
from random import randint
from subprocess import CalledProcessError, PIPE, run
import time
import netifaces
import yaml
from utils import (
    REST_PORT,
    REST_PREFIX,
    CONTROLLERS_LIST_FILE,
    get_controllers,
    get_charmstore_token,
    report_status
)
from charmhelpers.core import host, hookenv, unitdata
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


@when('config.changed.subnet')
def reconfigure_lxd():
    remove_state('lxd.configured')
    remove_state('lxd.subnet.full')
    remove_state('config.changed.subnet')


@when('apt.installed.lxd')
@when_not('lxd.init', 'lxd.init.failed')
def init_lxd():
    try:
        run(['lxd', 'init', '--auto'], stderr=PIPE, check=True)
    except CalledProcessError as e:
        if 'existing containers or images' not in e.stderr.decode('utf8'):
            set_state('lxd.init.failed')
            report_status()
            return
    set_state('lxd.init')


@when('lxd.init')
@when_not('lxd.configured')
@when_not('lxd.init.failed', 'lxd.subnet.failed', 'lxd.subnet.full')
def configure_lxd():
    # allow jenkins user to manage lxd
    utils.run_as('root', 'usermod', '-aG', 'lxd', 'jenkins')

    if not is_state('lxd.idmap.configured'):
        # enable ID mapping for the jenkins group
        user_info = pwd.getpwnam('jenkins')
        with Path('/etc/subuid').open('a') as fp:
            fp.write('root:{}:1\n'.format(user_info.pw_uid))
        with Path('/etc/subgid').open('a') as fp:
            fp.write('root:{}:1\n'.format(user_info.pw_gid))
        set_state('lxd.idmap.configured')

    subnet = hookenv.config('subnet')
    if not subnet:
        # pick a random subnet
        ifaddrs = [netifaces.ifaddresses(interface)
                   for interface in netifaces.interfaces()]
        subnets = ['{}.1/24'.format(ifaddr[2][0]['addr'])
                   for ifaddr in ifaddrs if '2' in ifaddr]
        for i in range(100):
            subnet = '10.{}.{}.1/24'.format(randint(0, 255), randint(0, 255))
            if subnet not in subnets:
                break
        else:
            set_state('lxd.subnet.full')
            return

    # enable container networking
    try:
        output = utils.run_as('root', 'lxc', 'network', 'list',
                              capture_output=True)
        if 'lxdbr0' not in output:
            utils.run_as('root', 'lxc', 'network', 'create', 'lxdbr0')

        config = {
            'ipv4.nat': 'true',
            'ipv4.address': subnet,
            'ipv6.nat': 'false',
            'ipv6.address': 'none',
        }
        for key, value in config.items():
            utils.run_as('root', 'lxc', 'network', 'set', 'lxdbr0', key, value)

        output = utils.run_as('root', 'lxc', 'profile', 'show', 'default',
                              capture_output=True)
        if 'lxdbr0' not in output:
            utils.run_as('root', 'lxc', 'network', 'attach-profile',
                         'lxdbr0', 'default', 'eth0')
    except CalledProcessError:
        set_state('lxd.subnet.failed')
        return

    # containers need to be privileged when run under the lxd/localhost
    # provider to make the root -> jenkins mapping and storage work
    utils.run_as('root', 'lxc', 'profile', 'set', 'default',
                 'security.privileged', 'true')

    set_state('lxd.configured')


@when('config.changed.cwrbox_keys')
@when_not('cwrbox.attached')
def update_trusted_keys():
    config = hookenv.config()
    keyring_file = Path('/var/lib/jenkins/.gnupg/cwrbox.gpg')
    if keyring_file.exists():
        keyring_file.unlink()
    remove_state('config.changed.cwrbox_keys')
    try:
        trusted_keys = yaml.safe_load(config['cwrbox_keys'])
        for key in trusted_keys:
            if len(key) < 40:
                raise ValueError('invalid key')
            elif len(key) == 40:
                utils.run_as('jenkins',
                             'gpg2', '--no-default-keyring',
                             '--keyring', 'cwrbox.gpg',
                             '--recv-keys', key)
            else:
                utils.run_as('jenkins',
                             'gpg2', '--no-default-keyring',
                             '--keyring', 'cwrbox.gpg',
                             '--import', '-',
                             input=key)
        remove_state('cwrbox.key.failed')
    except (ValueError, yaml.parser.ParserError, CalledProcessError):
        set_state('cwrbox.key.failed')
        utils.report_status()


@when('config.changed.cwrbox_image')
@when_not('cwrbox.attached')
def update_cwrbox_image():
    remove_state('cwrbox.imported')
    remove_state('config.changed.cwrbox_image')


@when('lxd.configured')
@when_not('cwrbox.imported')
def import_cwrbox():
    hookenv.status_set('maintenance', 'fetching cwrbox image')
    filename = hookenv.resource_get('cwrbox')
    filepath = filename and Path(filename)
    if filepath and filepath.exists() and filepath.stat().st_size:
        new_hash = host.file_hash(filename)
        old_hash = unitdata.kv().get('cwrbox.hash')
        if new_hash != old_hash:
            hookenv.status_set('maintenance', 'importing cwrbox image')
            try:
                utils.run_as('jenkins',
                             'lxc', 'image', 'import', filename,
                             '--alias', 'cwrbox')
            except CalledProcessError:
                set_state('cwrbox.image.failed')
                hookenv.log("Failed to import cwrbox image from resource")
                report_status()
                return
            unitdata.kv().set('cwrbox.hash', new_hash)
        image_url_file = Path('/var/lib/jenkins/cwrbox_image.url')
        if image_url_file.exists():
            image_url_file.unlink()
        set_state('cwrbox.attached')
    else:
        hookenv.status_set('maintenance', 'using remote image')
        image_url_file = Path('/var/lib/jenkins/cwrbox_image.url')
        image_url_file.write_text(hookenv.config('cwrbox_image'))
    remove_state('cwrbox.image.failed')
    set_state('cwrbox.imported')
    report_status()


@when('cwrbox.imported')
@when_not('juju-ci-env.installed')
def setup_ci_env():
    utils.run_as('root', 'pip', 'install', 'petname')

    # Make user jenkins parametrised. And this action as well
    with open("/etc/sudoers", "a") as sudoers:
        sudoers.write("%jenkins ALL=NOPASSWD: ALL\n")

    # TODO: this will need to be on shared storage to support scaling
    host.chownr("/srv/artifacts",
                owner="jenkins",
                group="jenkins",
                chowntopdir=True)

    scripts_dir = Path(hookenv.charm_dir()) / "scripts"
    host.symlink(str(scripts_dir), "/var/lib/jenkins/")

    mock_results_dir = Path(hookenv.charm_dir()) / "templates/output-results"
    host.symlink(str(mock_results_dir), "/var/lib/jenkins/mock-results")

    set_state('juju-ci-env.installed')
    report_status()


@when('jenkins.available', 'juju-ci-env.installed')
@when_not('jenkins.jobs.ready', 'jenkins.jobs.failed')
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
            # Retrying does not play well here.
            # I have seen a case where Jenkins mistakenly reports that
            # the plugin is installed causing an infinite retry loop :(
            # Here we report that jenkins failed and we block.
            set_state("jenkins.jobs.failed")
            return

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
    remove_state("cwrbox.imported")
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
