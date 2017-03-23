#!/usr/bin/env python3

import argparse
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
            bundlebuilder.execute(
                ["python3", "scripts/bundlebuilder.py", "foo"])

    def test_help(self):
        retcode, output = bundlebuilder.execute(
            ["python3", "scripts/bundlebuilder.py", "foo"],
            raise_exception=False)
        assert retcode is 2
        assert "invalid choice:" in output

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

    def test_parse_args_check(self):
        args = bundlebuilder.parse_args(
            ['check', 'github.com/foo', 'master', '.'])
        expected_args = argparse.Namespace(
            operation='check',
            repo='github.com/foo',
            branch='master',
            subdir='.',
        )
        self.assertEqual(args, expected_args)

    def test_parse_args_build(self):
        args = bundlebuilder.parse_args(
            ['build', 'github.com/foo', 'master', '.', '1', 'model1',
             'model2'])
        expected_args = argparse.Namespace(
            operation='build',
            repo='github.com/foo',
            branch='master',
            subdir='.',
            build_num='1',
            models=['model1', 'model2']
        )
        self.assertEqual(args, expected_args)


if __name__ == "__main__":
    unittest.main()
