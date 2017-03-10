#!/usr/bin/env python3

from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from shutil import rmtree
from tempfile import mkdtemp
from textwrap import dedent
from unittest import TestCase
from unittest.mock import patch, Mock

import charms
charms.layer = Mock()
with patch.object(charms, 'layer'):
    from actions.cwrhelpers import get_s3_credentials
    from actions.cwrhelpers import get_s3_options
    from actions.cwrhelpers import create_s3_config_file


class TestS3Credentials(TestCase):

    fake_creds = dedent("""\
    credentials:
        aws:
            default-credential: cred1
            cred2:
                auth-type: access-key
                access-key: foo
                secret-key: bar
            cred1:
                auth-type: access-key
                access-key: foo-2
                secret-key: bar-2
                """)
    fake_creds_no_default = dedent("""\
    credentials:
        aws:
            cred2:
                auth-type: access-key
                access-key: foo
                secret-key: bar
            cred1:
                auth-type: access-key
                access-key: foo-2
                secret-key: bar-2
                """)
    fake_creds_single = dedent("""\
    credentials:
        aws:
            cred:
                auth-type: access-key
                access-key: foo
                secret-key: bar
                """)
    fake_creds_no_aws = dedent("""\
    credentials:
        google:
            cred:
                auth-type: access-key
                access-key: foo
                secret-key: bar
                """)
    fake_creds_empty = dedent("""credentials: {}
    """)

    def test_get_s3_credentials(self):
        with patch('subprocess.check_output', autospec=True,
                   return_value=self.fake_creds)as co_mock:
            access, secret = get_s3_credentials('cred2')
        self.assertEqual(access, 'foo')
        self.assertEqual(secret, 'bar')
        co_mock.assert_called_once_with(
            ['juju', 'credentials', 'aws', '--format', 'yaml',
             '--show-secrets'])

    def test_get_s3_credentials_default_credential(self):
        with patch('subprocess.check_output', autospec=True,
                   return_value=self.fake_creds) as co_mock:
            access, secret = get_s3_credentials()
        self.assertEqual(access, 'foo-2')
        self.assertEqual(secret, 'bar-2')
        co_mock.assert_called_once_with(
            ['juju', 'credentials', 'aws', '--format', 'yaml',
             '--show-secrets'])

    def test_get_s3_credentials_single_credential(self):
        with patch('subprocess.check_output', autospec=True,
                   return_value=self.fake_creds_single) as co_mock:
            access, secret = get_s3_credentials()
        self.assertEqual(access, 'foo')
        self.assertEqual(secret, 'bar')
        co_mock.assert_called_once_with(
            ['juju', 'credentials', 'aws', '--format', 'yaml',
             '--show-secrets'])

    def test_get_s3_credentials_empty(self):
        with patch('subprocess.check_output', autospec=True,
                   return_value=self.fake_creds_empty) as co_mock:
            with patch('actions.cwrhelpers.fail_action', autospec=True,
                       side_effect=SystemExit) as fa_mock:
                with self.assertRaises(SystemExit):
                    get_s3_credentials()
        co_mock.assert_called_once_with(
            ['juju', 'credentials', 'aws', '--format', 'yaml',
             '--show-secrets'])
        fa_mock.assert_called_once_with(
            'AWS credentials not found. Set AWS credentials by running '
            '"set-credentials" action.')

    def test_get_s3_credentials_no_aws(self):
        with patch('subprocess.check_output', autospec=True,
                   return_value=self.fake_creds_no_aws) as co_mock:
            with patch('actions.cwrhelpers.fail_action', autospec=True,
                       side_effect=SystemExit) as fa_mock:
                with self.assertRaises(SystemExit):
                    get_s3_credentials()
        co_mock.assert_called_once_with(
            ['juju', 'credentials', 'aws', '--format', 'yaml',
             '--show-secrets'])
        fa_mock.assert_called_once_with(
            'AWS credentials not found. Set AWS credentials by running '
            '"set-credentials" action.')

    def test_get_s3_credentials_no_default(self):
        with patch('subprocess.check_output', autospec=True,
                   return_value=self.fake_creds_no_default) as co_mock:
            with patch('actions.cwrhelpers.fail_action', autospec=True,
                       side_effect=SystemExit) as fa_mock:
                with self.assertRaises(SystemExit):
                    get_s3_credentials()
        co_mock.assert_called_once_with(
            ['juju', 'credentials', 'aws', '--format', 'yaml',
             '--show-secrets'])
        fa_mock.assert_called_once_with(
            'Credentials not found. Set AWS credentials by running '
            '"set-credentials" action.')


class TestGetS3Options(TestCase):

    def test_create_s3_config_file(self):
        with NamedTemporaryFile() as s3_config:
            create_s3_config_file(s3_config.name, 'foo', 'bar')
            with open(s3_config.name) as f:
                creds = f.read()
        expected_output = dedent("""\
        [default]
        access_key = foo
        secret_key = bar
        """)
        self.assertEqual(creds, expected_output)

    def test_get_s3_options(self):
        with patch('actions.cwrhelpers.hookenv', autospec=True) as ch_mock:
            ch_mock.action_get.side_effect = fake_action_get
            with patch('subprocess.check_output', autospec=True,
                       return_value=TestS3Credentials.fake_creds
                       ) as co_mock:
                with NamedTemporaryFile() as s3_config:
                    s3_option = get_s3_options(s3_config.name)
        self.assertEqual(
            s3_option,
            '--bucket bucket-foo --results-dir results-dir-foo --s3-creds '
            '{} --s3-private'.format(s3_config.name))
        co_mock.assert_called_once_with(
            ['juju', 'credentials', 'aws', '--format', 'yaml',
             '--show-secrets'])

    def test_get_s3_options_public(self):
        with patch('actions.cwrhelpers.hookenv', autospec=True) as ch_mock:
            ch_mock.action_get.side_effect = fake_action_get_public
            with patch('subprocess.check_output', autospec=True,
                       return_value=TestS3Credentials.fake_creds
                       )as co_mock:
                with NamedTemporaryFile() as s3_config:
                    s3_option = get_s3_options(s3_config.name)
        self.assertEqual(
            s3_option,
            '--bucket bucket-foo --results-dir results-dir-foo --s3-creds '
            '{}'.format(s3_config.name))
        co_mock.assert_called_once_with(
            ['juju', 'credentials', 'aws', '--format', 'yaml',
             '--show-secrets'])

    def test_get_s3_options_no_bucket(self):
        with patch('actions.cwrhelpers.hookenv', autospec=True) as ch_mock:
            ch_mock.action_get.return_value = ''
            s3_option = get_s3_options(None)
        self.assertEqual(s3_option, '')


def fake_action_get(key):
    if key == "credential-name":
        return "cred1"
    if key == "private":
        return True
    return "{}-foo".format(key)


def fake_action_get_public(key):
    if key == "credential-name":
        return "cred1"
    if key == "private":
        return False
    return "{}-foo".format(key)


@contextmanager
def temp_dir():
    directory = mkdtemp()
    try:
        yield directory
    finally:
        rmtree(directory)
