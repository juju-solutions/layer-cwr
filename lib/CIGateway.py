from jenkins import Jenkins
from jujubigdata import utils
from subprocess import Popen, call


class CIGateway:

    @classmethod
    def start(cls, jenkins_url, jenkins_user, jenkins_pass, user='jenkins'):
        properties_path = "/var/lib/jenkins/CIGWServer.properties"
        with open(properties_path, 'w') as properties_file:
            properties_file.write("{}\n".format(jenkins_url))
            properties_file.write("{}\n".format(jenkins_user))
            properties_file.write("{}\n".format(jenkins_pass))

        cls._run_bg(user, './scripts/startflask.sh')

    @classmethod
    def stop(cls):
        call(['pkill', '-f', 'flask'])

    @classmethod
    def _run_bg(cls, user, command, *args):
        parts = [command] + list(args)
        quoted = ' '.join("'%s'" % p for p in parts)
        e = utils.read_etc_env()
        Popen(['su', user, '-c', '{}'.format(quoted)], env=e)

    @classmethod
    def get_current_jenkins(cls):
        properties_path = "/var/lib/jenkins/CIGWServer.properties"
        with open(properties_path, 'r') as properties_file:
            jenkins_url = properties_file.readline().rstrip('\n')
            jenkins_user = properties_file.readline().rstrip('\n')
            jenkins_pass = properties_file.readline().rstrip('\n')
        return Jenkins(jenkins_url, jenkins_user, jenkins_pass)
