import io
from subprocess import Popen, call
from jujubigdata import utils


class CIGateway:

    @classmethod
    def start(self, jenkinsurl, jenkinsuser, jenkinspass, user='jenkins'):
        with io.open("/var/lib/jenkins/CIGWServer.properties", 'w') as propertiesfile:
            propertiesfile.write("{}\n".format(jenkinsurl))
            propertiesfile.write("{}\n".format(jenkinsuser))
            propertiesfile.write("{}\n".format(jenkinspass))

        self._run_bg(user, './scripts/startflask.sh')

    @classmethod
    def stop(self):
        call(['pkill', '-f', 'flask'])

    @classmethod
    def _run_bg(self, user, command, *args):
        parts = [command] + list(args)
        quoted = ' '.join("'%s'" % p for p in parts)
        e = utils.read_etc_env()
        Popen(['su', user, '-c', '{}'.format(quoted)],
              env=e)
