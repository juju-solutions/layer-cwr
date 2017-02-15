#!/usr/bin/env python3

import sys
import os
import hashlib
from tempfile import mkdtemp
from time import sleep
from subprocess import Popen, PIPE, STDOUT
from shutil import rmtree
from yaml import safe_load, dump
from re import search

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib'))
from utils import get_fname  # noqa: E402


def execute(cmd, raise_exception=True):
    """
    Execute bash script printing the stdout and stderr without delay.

    Args:
        cmd: a list with the command
        raise_exception: If True, will raise an exception upon a failing script

    Returns: a tuple of return_code, output

    """
    print("Running {}".format(" ".join(cmd)))
    output = ""
    with Popen(cmd, stdout=PIPE, stderr=STDOUT, bufsize=1, universal_newlines=True) as p:
        for line in p.stdout:
            output += line
            print(line, end='')

        # Wait until process terminates
        while p.poll() is None:
            sleep(1)

        if raise_exception and p.returncode != 0:
            raise Exception("Command {} failed with {}".format(" ".join(cmd), p.returncode))
        else:
            return p.returncode, output


class Bundle(object):

    def __init__(self,
                 repo,
                 branch,
                 ci_info_file=None,
                 CWR_dry_run=False,
                 store_push_dry_run=False,
                 fake_output=""):
        """
        Grab the bundle source and initialise the object.

        Args:
            repo: repository to grab the bundle from
            branch: branch to grab the bundle from
            ci_info_file: override the bundle's ci-info.yaml file
            CWR_dry_run: perform a dry run on running the tests
            store_push_dry_run: perform a dry run on pushing to the store
            fake_output: path to a tarball with fake output
        """
        self.tempdir = mkdtemp()
        execute(["git", "clone", repo, "--branch", branch, "{}/".format(self.tempdir)])
        with open("{}/bundle.yaml".format(self.tempdir), 'r+') as stream:
            self.bundle = safe_load(stream)

        # Load the ci-info.yaml
        if ci_info_file:
            with open(ci_info_file, 'r+') as stream:
                self.ci_info = safe_load(stream)
        elif os.path.isfile("{}/ci-info.yaml".format(self.tempdir)):
            with open("{}/ci-info.yaml".format(self.tempdir), 'r+') as stream:
                self.ci_info = safe_load(stream)
        else:
            self.ci_info = dict()  # or load some default ci_info

        self.location = "cs:~{}/{}".format(self.ci_info['bundle']['namespace'], self.ci_info['bundle']['name'])
        self.upgraded = False
        self.fake_output = fake_output

        # We keep the sha1 digest/signature of the last bundle for
        # which we triggered a build in the follwing file
        self.signature_file = "last_bundle.signature"
        if CWR_dry_run:
            self.CWR_command = ["echo", "cwr"]
        else:
            self.CWR_command = ["cwr"]

        if store_push_dry_run:
            self.charm_command = ["echo", "charm"]
        else:
            self.charm_command = ["charm"]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        rmtree(self.tempdir)

    def get_charms(self):
        """
        Get the charms of the bundle.

        Returns: the list of charm names.

        """
        charms = []
        services = self.bundle['services'].values()
        for service in services:
            charms.append(service['charm'])
        return charms

    def get_charms_upgrade_policy(self, charm_name):
        """
        Scan the ci-info.yaml and return the upgrade instructions
        for the provided charm
        Args:
            charm_name: name of the charm to be upgraded

        Returns: dictionary with upgrade instructions or None

        """
        if charm_name in self.ci_info['charm-upgrade'].keys():
            return self.ci_info['charm-upgrade'][charm_name]
        else:
            return None

    def upgrade(self, charm, new_revision):
        """
        Try to update the bundle.yaml with the revision of the charm provided.
        If an upgrade is actually possible, the self.upgraded flag is set.
        Args:
            charm: the name of the charm
            new_revision: the revision of the charm

        """
        services = self.bundle['services'].values()
        for service in services:
            if service['charm'] == charm and service['charm'] != new_revision:
                service['charm'] = new_revision
                self.upgraded = True
                with open("{}/bundle.yaml".format(self.tempdir), 'w') as fp:
                    dump(self.bundle, fp)

    def upgradable(self):
        """
        Is an upgrade possible?

        Returns: True if an upgrade of the bundle is possible.

        """
        return self.upgraded

    def should_trigger_build(self):
        """
        Should a build be triggered?
        To answer this we need:
        a) to have new charms for the bundle
        b) to make sure we have not triggered a build in the past.

        Returns: True if a new build should be triggered

        """
        if not self.upgradable():
            return False

        # Bundle is upgradable from here on
        if not os.path.isfile(self.signature_file):
            self.store_signature()
            return True
        else:
            last_digest = self.get_last_signature()
            current_digest = self.get_current_signature()
            if last_digest != current_digest:
                self.store_signature()
                return True
            else:
                return False

    def get_current_signature(self):
        """
        Get the sha1 digest of the bundle we have so far.

        Returns: sha1 digest of bundle

        """

        with open("temp_bundle.yaml", 'w') as fp:
            dump(self.bundle, fp)

        sha1 = hashlib.sha1()
        with open("temp_bundle.yaml", 'rb') as f:
            data = f.read()
            sha1.update(data)
        return sha1.hexdigest()

    def get_last_signature(self):
        """
        Get the digest of the bundle we last fired a build for.

        Returns: string digest

        """
        with open(self.signature_file, 'r') as fp:
            digest = fp.read()
        return digest

    def store_signature(self):
        """
        Store the digest of the current bundle.

        Returns: string digest

        """
        digest = self.get_current_signature()
        with open(self.signature_file, 'w') as f:
            f.write(digest)
        return digest

    def test(self, build_num, models):
        """
        Run tests on the bundle.

        Args:
            build_num: Build ID number
            models: the juju model to be used for deployments.

        """
        with open('totest.yaml', 'w') as f:
            f.write("bundle: {}\n".format(self.tempdir))
            f.write("bundle_name: build-bundle-{}\n".format(get_fname(self.ci_info['bundle']['name'])))
            f.write("bundle_file: bundle.yaml\n")

        if self.fake_output == "":
            cmd = list(self.CWR_command)
            cmd += ["-F"]
            cmd += ["--results-dir", "/srv/artifacts"]
            cmd += ["--test-id", build_num]
            cmd += models
            cmd += ["totest.yaml"]
            execute(cmd)
        else:
            output_dir = "/srv/artifacts/{}/{}/".format(os.environ['JOB_NAME'], build_num)
            cmd_str = "tar -zxvf {} -C {}".format(self.fake_output, output_dir)
            cmd = cmd_str.split()
            execute(cmd)
            if "output-results/pass" not in self.fake_output:
                raise Exception("Faking a failing CWR")

    def release(self):
        """
        Push, release and grant permissions to everyone for the bundle.

        Returns: True if the release process was successful

        """
        if not self.ci_info['bundle']['release']:
            return False

        cmd = list(self.charm_command)
        cmd += ["push", self.tempdir, self.location]
        execute(cmd)

        _, output = execute(["charm", "show", self.location, "-c", "unpublished", "id"])
        latest = safe_load(output)
        just_released = latest['id']['Id']

        cmd = list(self.charm_command)
        cmd += ["release", just_released]
        cmd += ["--channel", self.ci_info['bundle']['to-channel']]
        execute(cmd)

        cmd = list(self.charm_command)
        cmd += ["grant", just_released]
        cmd += ["everyone"]
        _, output = execute(cmd)

        return True


class Charm(object):

    def __init__(self, charm_name, store_push_dry_run=False):
        """
        Initialise this helper class.

        Args:
            charm_name: the name of the charm
            store_push_dry_run: should we fake the push to store
        """
        self.provided_name = charm_name
        self.name_no_namespace = charm_name[charm_name.rfind('/')+1:]
        m = search(r'\-\d+$', self.name_no_namespace)
        # if the string ends in digits m will be a Match object, or None otherwise.
        self.name = self.name_no_namespace
        self.name_no_revision = charm_name
        if m is not None:
            self.name = self.name[:len(self.name) - len(m.group())]
            self.name_no_revision = charm_name[:len(charm_name) - len(m.group())]

        if store_push_dry_run:
            self.charm_command = ["echo", "charm"]
        else:
            self.charm_command = ["charm"]

    def get_latest(self, channel):
        """
        Get the latest revision of the charm present in the channel provided

        Args:
            channel: the channel to look for the charm

        Returns: the latest revision of the charm

        """
        _, output = execute(["charm", "show", self.name_no_revision, "-c", channel, "id"])
        latest = safe_load(output)
        return latest['id']['Id']

    def get_name(self):
        """
        Returns: the name of the charm

        """
        return self.name

    def get_namespace_name(self):
        """

        Returns: the name of the charm withou the revision

        """
        return self.name_no_revision

    def get_namespace_name_revision(self):
        """
        Returns: the charm as provided in this class (namespace/name-revision)

        """
        return self.provided_name

    def release_latest(self, from_channel, to_channel):
        """
        Release the latest revision of the charm in the from_channel
        to the to_channel

        Args:
            from_channel: where to get the latest charm from
            to_channel: where to release the charm

        """
        latest = self.get_latest(from_channel)
        cmd = list(self.charm_command)
        cmd += ["release", latest]
        cmd += ["--channel", to_channel]
        execute(cmd)
        latest_just_released = self.get_latest(to_channel)
        cmd = list(self.charm_command)
        cmd += ["grant", latest_just_released]
        cmd += ["everyone"]
        execute(cmd)


class Coordinator(object):

    def __init__(self, CWR_dry_run=False, store_push_dry_run=False):
        self.CWR_dry_run = CWR_dry_run
        self.store_push_dry_run = store_push_dry_run

    def check_bundle(self, repo, branch):
        """
        See if the bundle needs to be updated
        Args:
            repo: repository to grab the bundle from
            branch: branch  to grab the bundle from

        Returns: True if a newer version of a charm is present

        """
        with Bundle(repo, branch,
                    CWR_dry_run=self.CWR_dry_run,
                    store_push_dry_run=self.store_push_dry_run) as bundle:
            print("Checking {}".format(repo))
            charms = bundle.get_charms()
            print("Charms in bunlde {}".format(charms))
            for charm in charms:
                c = Charm(charm)
                upgrade_info = bundle.get_charms_upgrade_policy(c.get_name())
                if upgrade_info:
                    print("Upgrading charm {}".format(charm))
                    print("Upgrading info {}".format(upgrade_info))
                    print("Latest revision {} in channel {}"
                          .format(c.get_latest(upgrade_info["from-channel"]),
                                  upgrade_info["from-channel"]))
                    bundle.upgrade(charm, c.get_latest(upgrade_info["from-channel"]))
                else:
                    print("Charm {} not marked for upgrade.".format(c.get_name()))

            if not bundle.upgradable():
                print("Not upgradable")
                return False
            else:
                print("Upgraded")
                if bundle.should_trigger_build():
                    print("Should trigger build")
                    return True
                else:
                    return False

    def test_and_release_bundle(self, repo, branch, build_num, models):
        """
        Build, test and release the bundle
        Args:
            repo: repository to grab the bundle from
            branch: branch  to grab the bundle from
            build_num: Build ID number
            models: Juju models to use for testing the bundle

        """
        with Bundle(repo, branch,
                    CWR_dry_run=self.CWR_dry_run,
                    store_push_dry_run=self.store_push_dry_run,
                    fake_output=os.environ['OUTPUT_SCENARIO']) as bundle:
            print("Checking {}".format(repo))
            charms = bundle.get_charms()
            print("Charms in bundle {}".format(charms))
            for charm in charms:
                c = Charm(charm)
                upgrade_info = bundle.get_charms_upgrade_policy(c.get_name())
                if upgrade_info:
                    print("Upgrading {}".format(charm))
                    print("Upgrading info {}".format(upgrade_info))
                    print("Upgrading to revision {} of channel {}"
                          .format(c.get_latest(upgrade_info["from-channel"]),
                                  upgrade_info["from-channel"]))
                    bundle.upgrade(charm, c.get_latest(upgrade_info["from-channel"]))
            print("Testing new bundle")
            bundle.test(build_num, models)
            print("Releasing bundle")
            bundle.release()
            for charm in charms:
                c = Charm(charm)
                upgrade_info = bundle.get_charms_upgrade_policy(c.get_name())
                if upgrade_info and upgrade_info['release']:
                    print("Releasing charm {} from channel {} to channel {}"
                          .format(c.get_latest(upgrade_info["from-channel"]),
                                  upgrade_info["from-channel"],
                                  upgrade_info['to-channel']))
                    c.release_latest(upgrade_info['from-channel'], upgrade_info['to-channel'])


if __name__ == "__main__":
    if "--help" in sys.argv or len(sys.argv) == 1:
        print("Usage: {} <operation> <repo> <branch> <model>\n".format(sys.argv[0]))
        print("  <operation>: 'check' or 'build' to check or build the bundle.")
        print("  <repo>: repo of the bundle.")
        print("  <branch>: branch to grab the bundle from.")
        print("  <build_id>: id of the build.")
        print("  <list of models>: models to be used for testing. Needed only for 'build' operation.")
        sys.exit(1)
    operation = sys.argv[1]
    repo = sys.argv[2]
    branch = sys.argv[3]
    tester = Coordinator()
    if operation == "check":
        if tester.check_bundle(repo, branch):
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        build_num = sys.argv[4]
        models = sys.argv[5:]
        tester.test_and_release_bundle(repo, branch, build_num, models)
        sys.exit(0)
