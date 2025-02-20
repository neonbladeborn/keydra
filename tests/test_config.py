import copy
import unittest

from keydra.config import KeydraConfig

from keydra.exceptions import ConfigException

from unittest.mock import MagicMock
from unittest.mock import patch


ENVS = {
    'dev': {
        'description': 'AWS Development Environment',
        'type': 'aws',
        'access': 'dev',
        'id': '001122',
        'secrets': [
            'aws_deployments',
            'splunk',
            'aws_deployment_just_rotate',
            'cloudflare_canary',
            'okta_canary',
            'office365_adhoc',
        ]
    },
    'uat': {
        'description': 'AWS UAT Environment',
        'type': 'aws',
        'access': 'uat',
        'id': '334455',
        'secrets': ['aws_deployments']
    },
    'prod': {
        'description': 'AWS Prod Environment',
        'type': 'aws',
        'access': 'production',
        'id': 667788,
        'secrets': ['aws_deployments']
    },
    'control': {
        'description': 'AWS Master Environment',
        'type': 'aws',
        'access': 'production',
        'id': 991122,
        'secrets': ['aws_deployments']
    },
}


SECRETS = {
    'aws_deployments':
    {
        'key': 'km_managed_api_user',
        'provider': 'IAM',
        'rotate': 'nightly',
        'distribute': [
            {
                'key': 'KM_{ENV}_AWS_ACCESS_ID',
                'provider': 'bitbucket',
                'source': 'key',
                'envs': [
                  '*'
                ],
                'config': {
                    'scope': 'account'
                }
            },
            {
                'key': 'KM_{ENV}_AWS_SECRET_ACCESS_KEY',
                'provider': 'bitbucket',
                'source': 'secret',
                'envs': [
                    '*'
                ],
                'config': {
                    'scope': 'account'
                }
            },
            {
                'key': 'KM_MANAGED_AWS_ACCESS_ID',
                'provider': 'bitbucket',
                'source': 'key',
                'envs': [
                    'dev'
                ],
                'config': {
                    'scope': 'account'
                }
            },
            {
                'key': 'KM_MANAGED_AWS_SECRET_ACCESS_KEY',
                'provider': 'bitbucket',
                'source': 'secret',
                'envs': [
                    'dev'
                ],
                'config': {
                    'scope': 'account'
                }
            }
        ]
    },
    'aws_deployment_just_rotate':
    {
        'key': 'km_managed_just_rotate',
        'provider': 'IAM',
        'rotate': 'nightly'
    },
    'splunk':
    {
        'key': 'splunk',
        'provider': 'salesforce',
        'rotate': 'monthly'
    },
    'cloudflare_canary':
    {
        'key': 'cloudflare_canary_key',
        'provider': 'cloudflare',
        'rotate': 'canaries'
    },
    'okta_canary':
    {
        'key': 'okta_canary_key',
        'provider': 'okta',
        'rotate': 'canaries'
    },
    'office365_adhoc':
    {
        'key': 'control_secrets',
        'provider': 'office365',
        'rotate': 'adhoc'
    }
}


SECRETS_S = {
    'splunk':
    {
        'key': 'splunk',
        'provider': 'salesforce',
        'rotate': 'monthly',
        'distribute': [{'provider': 'secretsmanager', 'envs': ['dev']}]
    }
}


ENV_CONFIG = {
    'provider': 'bitbucket',
    'config': {
        'account_username': 'acct_user',
        'secrets': {
            'repository': 'secrets_repo',
            'path': 'secrets_path',
            'filetype': 'secrets_filetype'
        },
        'environments': {
            'repository': 'envs_repo',
            'path': 'envs_path',
            'filetype': 'envs_filetype'
        }
    }
}


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.client = KeydraConfig(
            session=self.session,
            config=ENV_CONFIG
        )

    def test__dodgy_config(self):
        with self.assertRaises(ConfigException):
            KeydraConfig(
                session=MagicMock(),
                config={}
            )

        with self.assertRaises(ConfigException):
            KeydraConfig(
                session=MagicMock(),
                config={'provider': {}}
            )

    def test__validate_spec_environments(self):
        envs = copy.deepcopy(ENVS)
        secrets = copy.deepcopy(SECRETS)

        self.client._validate_spec(envs, secrets)

        envs['prod'].pop('type')

        with self.assertRaises(ConfigException):
            self.client._validate_spec(envs, secrets)

        envs = copy.deepcopy(ENVS)

        envs['prod'].pop('id')

        with self.assertRaises(ConfigException):
            self.client._validate_spec(envs, secrets)

        with self.assertRaises(ConfigException):
            secrets = copy.deepcopy(SECRETS)

            secrets['aws_deployments']['distribute'][0]['envs'] = ['notanenv']
            self.client._validate_spec(ENVS, secrets)

    def test__validate_spec_secrets(self):
        envs = copy.deepcopy(ENVS)
        secrets = copy.deepcopy(SECRETS)

        self.client._validate_spec(envs, secrets)

        secrets['aws_deployments'].pop('provider')

        with self.assertRaises(ConfigException):
            self.client._validate_spec(envs, secrets)

        secrets = copy.deepcopy(SECRETS)

        secrets['aws_deployments'].pop('key')

        with self.assertRaises(ConfigException):
            self.client._validate_spec(envs, secrets)

        secrets = copy.deepcopy(SECRETS)

        secrets['aws_deployments']['distribute'][0].pop('provider')

        with self.assertRaises(ConfigException):
            self.client._validate_spec(envs, secrets)

    def test__guess_current_environment(self):
        with patch.object(self.client, '_fetch_current_account') as mk_fca:
            mk_fca.return_value = 334455
            self.assertEquals(
                self.client._guess_current_environment(ENVS), 'uat'
            )

            mk_fca.return_value = 667788
            self.assertEquals(
                self.client._guess_current_environment(ENVS), 'prod'
            )

            mk_fca.return_value = 999999
            with self.assertRaises(ConfigException):
                self.client._guess_current_environment(ENVS)

    def test__filter(self):
        with patch.object(
            self.client, '_guess_current_environment'
        ) as mk_gce:

            mk_gce.return_value = 'prod'
            filtered = self.client._filter(ENVS, SECRETS, rotate='nightly')
            self.assertEqual(len(filtered), 1)
            self.assertEqual(len(filtered[0]['distribute']), 2)

            mk_gce.return_value = 'dev'
            filtered = self.client._filter(ENVS, SECRETS, rotate='nightly')
            self.assertEqual(len(filtered), 2)
            self.assertEqual(filtered[0]['key'], 'km_managed_api_user')
            self.assertEqual(len(filtered[0]['distribute']), 4)

            mk_gce.return_value = 'dev'
            filtered = self.client._filter(
                ENVS, SECRETS, requested_secrets=[], rotate='nightly'
            )
            self.assertEqual(len(filtered), 2)
            self.assertEqual(filtered[0]['key'], 'km_managed_api_user')
            self.assertEqual(len(filtered[0]['distribute']), 4)

            mk_gce.return_value = 'dev'
            filtered = self.client._filter(
                ENVS,
                SECRETS,
                requested_secrets=['aws_deployment_just_rotate'],
                rotate='nightly'
            )
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]['key'], 'km_managed_just_rotate')

            mk_gce.return_value = 'dev'
            filtered = self.client._filter(ENVS, SECRETS, rotate='monthly')
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]['key'], 'splunk')

            mk_gce.return_value = 'dev'
            filtered = self.client._filter(ENVS, SECRETS_S, rotate='monthly')
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]['key'], 'splunk')
            self.assertEqual(
                filtered[0]['distribute'][0]['provider'], 'secretsmanager'
            )

            mk_gce.return_value = 'dev'
            filtered = self.client._filter(
                ENVS, SECRETS_S, rotate='adhoc', requested_secrets=['splunk']
            )
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]['key'], 'splunk')
            self.assertEqual(
                filtered[0]['distribute'][0]['provider'], 'secretsmanager'
            )

            mk_gce.return_value = 'dev'
            filtered = self.client._filter(ENVS, SECRETS, rotate='canaries')
            self.assertEqual(len(filtered), 2)
            self.assertEqual(filtered[0]['key'], 'cloudflare_canary_key')
            self.assertEqual(filtered[1]['key'], 'okta_canary_key')

    @patch('keydra.loader.build_client')
    def test_load_secret_specs(self, mk_bc):
        with patch.object(self.client, '_filter') as mk_fba:
            with patch.object(self.client, '_validate_spec') as mk_vc:
                self.client.load_secrets()

                mk_bc.assert_called_once_with(ENV_CONFIG['provider'], None)
                mk_fba.assert_called()
                mk_vc.assert_called()
