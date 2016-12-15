#!/usr/bin/env python3

import sys
import os
import subprocess
import shutil
import yaml
import re
import hashlib
import tempfile
import logging


class Bundle:

    def __init__(self, repo, ci_info_file=None, BT_dry_run=False, store_push_dry_run=False):
        self.tempdir = tempfile.mkdtemp()
        subprocess.check_output(["git", "clone", repo, "{}/".format(self.tempdir)])
        with open("{}/bundle.yaml".format(self.tempdir), 'r+') as stream:
            self.bundle = yaml.safe_load(stream)

        if ci_info_file:
            with open(ci_info_file, 'r+') as stream:
                self.ci_info = yaml.safe_load(stream)
        elif os.path.isfile("{}/ci-info.yaml".format(self.tempdir)):
            with open("{}/ci-info.yaml".format(self.tempdir), 'r+') as stream:
                self.ci_info = yaml.safe_load(stream)
        else:
            self.ci_info = dict() # or load some default ci_info

        self.localtion = "cs:~{}/{}".format(self.ci_info['bundle']['namespace'], self.ci_info['bundle']['name'])
        self.upgraded = False
        self.signature_file = "last_bundle.signature"
        if BT_dry_run:
            self.BT_command = ["echo", "bundletester"]
        else:
            self.BT_command = ["bundletester"]

        if store_push_dry_run:
            self.charm_command = ["echo", "charm"]
        else:
            self.charm_command = ["charm"]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self.tempdir)

    def get_charms(self):
        charms = []
        services = self.bundle['services'].values()
        for service in services:
            charms.append(service['charm'])
        return charms

    def get_charms_upgrade_policy(self, charm_name):
        if charm_name in self.ci_info['charm-upgrade'].keys():
            return self.ci_info['charm-upgrade'][charm_name]
        else:
            return None

    def upgrade(self, charm, new_revision):
        services = self.bundle['services'].values()
        for service in services:
            if service['charm'] == charm and service['charm'] != new_revision:
                service['charm'] = new_revision
                self.upgraded = True
                with open("{}/bundle.yaml".format(self.tempdir), 'w') as fp:
                    yaml.dump(self.bundle, fp)

    def upgradable(self):
        return self.upgraded

    def should_trigger_build(self):
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
        with open("temp_bundle.yaml", 'w') as fp:
            yaml.dump(self.bundle, fp)

        sha1 = hashlib.sha1()
        with open("temp_bundle.yaml", 'rb') as f:
            data = f.read()
            sha1.update(data)
        return sha1.hexdigest()

    def get_last_signature(self):
        with open(self.signature_file, 'r') as fp:
            digest = fp.read()
        return digest

    def store_signature(self):
        digest = self.get_current_signature()
        with open(self.signature_file, 'w') as f:
            f.write(digest)
        return digest

    def test(self, model):
        cmd = list(self.BT_command)
        cmd += ["-vFt", self.tempdir]
        cmd += ["-e", model]
        cmd += ["-e", model]
        cmd += ["--bundle", "bundle.yaml"]
        subprocess.check_output(cmd)

    def release(self):
        if not self.ci_info['bundle']['release']:
            return False

        cmd = list(self.charm_command)
        cmd += ["push", self.tempdir, self.localtion]
        cmd += ["--channel", self.ci_info['bundle']['to-channel']]
        output = subprocess.check_output(cmd)
        logging.warning("During release, calling {} with output {}".format(cmd, output))

        output = subprocess.check_output(["charm", "show", self.localtion, "-c", self.ci_info['bundle']['to-channel'], "id"])
        logging.warning("During release, just released {}".format(output))
        latest = yaml.safe_load(output)
        just_released = latest['id']['Id']

        cmd = list(self.charm_command)
        cmd += ["grant", just_released]
        cmd += ["everyone"]
        output = subprocess.check_output(cmd)
        logging.warning("During release, grant to everyone with {} and output {}".format(cmd, output))

        return True



class Charm:

    def __init__(self, charm_name, store_push_dry_run=False):
        self.provided_name = charm_name
        self.name_no_namespace = charm_name[charm_name.rfind('/')+1:]
        m = re.search(r'\-\d+$', self.name_no_namespace)
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
        output = subprocess.check_output(["charm", "show", self.name_no_revision, "-c", channel, "id"])
        latest = yaml.safe_load(output)
        return latest['id']['Id']

    def get_name(self):
        return self.name

    def get_namespace_name(self):
        return self.name_no_revision

    def get_namespace_name_revision(self):
        return self.provided_name

    def release_latest(self, from_channel, to_channel):
        latest = self.get_latest(from_channel)
        cmd = list(self.charm_command)
        cmd += ["release", latest]
        cmd += ["--channel", to_channel]
        subprocess.check_output(cmd)
        latest_just_released = self.get_latest(to_channel)
        cmd = list(self.charm_command)
        cmd += ["grant", latest_just_released]
        cmd += ["everyone"]
        subprocess.check_output(cmd)


class Tester:

    def __init__(self, BT_dry_run=False, store_push_dry_run=False):
        self.BT_dry_run = BT_dry_run
        self.store_push_dry_run = store_push_dry_run

    def check_bundle(self, repo):
        with Bundle(repo, "ci-info.yaml", self.BT_dry_run, self.store_push_dry_run) as bundle:
            print("Checking {}".format(repo))
            charms = bundle.get_charms()
            print("{}".format(charms))
            for charm in charms:
                c = Charm(charm)
                print("{}".format(c.get_name()))
                print("Latest {}".format(c.get_latest("stable")))
                upgrade_info = bundle.get_charms_upgrade_policy(c.get_name())
                if upgrade_info:
                    print("Upgrading {}".format(charm))
                    print("Upgrading info {}".format(upgrade_info))
                    bundle.upgrade(charm, c.get_latest(upgrade_info["from-channel"]))
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

    def test_and_release_bundle(self, repo, model):
        with Bundle(repo, "ci-info.yaml", self.BT_dry_run, self.store_push_dry_run) as bundle:
            print("Checking {}".format(repo))
            charms = bundle.get_charms()
            print("{}".format(charms))
            for charm in charms:
                c = Charm(charm)
                print("{}".format(c.get_name()))
                print("Latest {}".format(c.get_latest("stable")))
                upgrade_info = bundle.get_charms_upgrade_policy(c.get_name())
                if upgrade_info:
                    print("Upgrading {}".format(charm))
                    print("Upgrading info {}".format(upgrade_info))
                    bundle.upgrade(charm, c.get_latest(upgrade_info["from-channel"]))
            bundle.test(model)
            bundle.release()
            for charm in charms:
                c = Charm(charm)
                print("{}".format(c.get_name()))
                print("Latest {}".format(c.get_latest("stable")))
                upgrade_info = bundle.get_charms_upgrade_policy(c.get_name())
                if upgrade_info and upgrade_info['release']:
                    print("Upgrading {}".format(charm))
                    print("Upgrading info {}".format(upgrade_info))
                    c.release_latest(upgrade_info['from-channel'], upgrade_info['to-channel'])


operation = {{operation}}
tester = Tester(BT_dry_run=True, store_push_dry_run=True)
if operation == "check":
    tester.check_bundle({{repo}})
else:
    tester.test_and_release_bundle({{repo}}, {{model}})
