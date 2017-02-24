#!/usr/bin/env python3

import os
import unittest
from scripts import bundlebuilder
from unittest.mock import patch, mock_open


class TestBundlebuilder(unittest.TestCase):

    bundle_yaml = "bundle:\n namespace: foo\n name: bar"

    def test_execute(self):
        retcode, output = bundlebuilder.execute(["ls", "-l"])
        assert retcode is 0

    def test_raise(self):
        with self.assertRaises(Exception):
            retcode, output = bundlebuilder.execute(
                ["python3", "scripts/bundlebuilder.py", "--help"])

    def test_help(self):
        retcode, output = bundlebuilder.execute(
            ["python3", "scripts/bundlebuilder.py", "--help"],
            raise_exception=False)
        assert retcode is 1
        assert "Usage:" in output

    @patch('scripts.bundlebuilder.execute')
    def test_bundle(self, execute_mock):
        with patch.dict(os.environ, {'JOB_NAME': 'build-bundle-mybundle'}):
            with patch("builtins.open", mock_open(read_data=self.bundle_yaml)):
                bundle = bundlebuilder.Bundle(
                    "http://github/myrepo",
                    "mybranch",
                    "insidedir",
                    "myci-info.yaml",
                    CWR_dry_run=True,
                    store_push_dry_run=True)
                bundle.test(build_num=1, controllers=["lxd", "aws"])
                assert execute_mock.call_count is 2

    @patch('scripts.bundlebuilder.execute')
    def test_charm(self, execute_mock):
        execute_mock.return_value = (0, "id:\n Id: cs:~me/ubuntu-1")
        charm = bundlebuilder.Charm("cs:~me/ubuntu", store_push_dry_run=True)
        assert "ubuntu" == charm.get_name()
        assert "cs:~me/ubuntu" == charm.get_namespace_name_revision()
        charm.release_latest("edge", "beta")
        print(execute_mock.call_count)
        assert execute_mock.call_count is 4


if __name__ == "__main__":
    unittest.main()
