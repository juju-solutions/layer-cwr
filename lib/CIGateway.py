from pathlib import Path
import subprocess

from jenkins import Jenkins
from charmhelpers.core import hookenv, host
from charmhelpers.core import templating


class CIGateway:

    @classmethod
    def start(cls, jenkins_url, jenkins_user, jenkins_pass, user='jenkins'):
        Path("/var/lib/jenkins/CIGWServer.properties").write_text("\n".join([
            jenkins_url,
            jenkins_user,
            jenkins_pass,
        ]))

        host.mkdir("/var/log/cwr-server",
                   owner='ubuntu',
                   group='ubuntu',
                   perms=0o755)

        templating.render(
            source="cwr-server.service",
            target="/etc/systemd/system/cwr-server.service",
            context={
                'charm_dir': hookenv.charm_dir()
            })

        subprocess.check_call(['systemctl', 'daemon-reload'])
        host.service_start('cwr-server')

    @classmethod
    def stop(cls):
        host.service_stop('cwr-server')

    @classmethod
    def restart(cls):
        host.service_restart('cwr-server')

    @classmethod
    def get_current_jenkins(cls):
        properties_path = "/var/lib/jenkins/CIGWServer.properties"
        with open(properties_path, 'r') as properties_file:
            jenkins_url = properties_file.readline().rstrip('\n')
            jenkins_user = properties_file.readline().rstrip('\n')
            jenkins_pass = properties_file.readline().rstrip('\n')
        return Jenkins(jenkins_url, jenkins_user, jenkins_pass)
