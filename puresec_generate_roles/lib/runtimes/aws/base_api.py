""" Methods for AWS API. """

from collections import defaultdict
from functools import partial
from lib.utils import eprint
import abc
import boto3
import botocore
import re

class BaseApi:
    __metaclass__ = abc.ABCMeta

    ARN_RESOURCE_PATTERN = re.compile(r"^arn:.*:(.+?)$")

    SERVICE_RESOURCES_PROCESSOR = {
            # service: function(self, filename, file, resources, region, account)
            'dynamodb': lambda self: partial(self._get_generic_resources, resource_format="table/{}",
                                             get_all_resources_method=partial(self._get_generic_all_resources, 'dynamodb', api_method='list_tables', api_attribute='TableNames')),
            'kinesis':  lambda self: partial(self._get_generic_resources, resource_format="stream/{}",
                                             get_all_resources_method=partial(self._get_generic_all_resources, 'kinesis', api_method='list_streams', api_attribute='StreamNames')),
            'kms':      lambda self: partial(self._get_generic_resources, resource_format="key/{}",
                                             get_all_resources_method=partial(self._get_generic_all_resources, 'kms', api_method='list_keys', api_attribute='Keys', api_inner_attribute='KeyId')),
            'lambda':   lambda self: partial(self._get_generic_resources, resource_format="function/{}",
                                             get_all_resources_method=partial(self._get_generic_all_resources, 'lambda', api_method='list_functions', api_attribute='Functions', api_inner_attribute='FunctionName')),
            's3':       lambda self: partial(self._get_generic_resources, resource_format="{}",
                                             get_all_resources_method=partial(self._get_generic_all_resources, 's3', api_method='list_buckets', api_attribute='Buckets', api_inner_attribute='Name')),
            'sns':      lambda self: partial(self._get_generic_resources, resource_format="{}",
                                             get_all_resources_method=partial(self._get_generic_all_resources, 'sns', api_method='list_topics', api_attribute='Topics', api_inner_attribute='TopicArn',
                                                                              resource_converter=lambda topic_arn: ARN_RESOURCE_PATTERN.match(topic_arn).group(1))),
            'states':   lambda self: self._get_states_resources,
            }

    REGIONLESS_SERVICES = (
            's3',
            )

    SERVICE_RESOURCELESS_ACTIONS = {
            'dynamodb': tuple(
                # "CreateBucket" -> "s3:CreateBucket"
                "dynamodb:{}".format(method)
                for method in
                (
                    'DescribeLimits', 'DescribeReservedCapacity', 'DescribeReservedCapacityOfferings', 'ListTables', 'PurchaseReservedCapacityOfferings',
                    )
            ),
            's3': tuple(
                # "CreateBucket" -> "s3:CreateBucket"
                "s3:{}".format(method)
                for method in
                (
                    'CreateBucket',
                    )
            ),
        }

    # { (client, api_method, api_kwargs): { resource: resource_pattern } } }
    RESOURCE_CACHE = {}
    def _get_cached_api_result(self, service, region, account, api_method, api_kwargs={}):
        client = self._get_client(service, region, account)
        if client is None:
            eprint("error: cannot create {} client for region: '{}', account: '{}'".format(service, region, account))
            return

        cache_key = (client, api_method, frozenset(api_kwargs.items()))

        result = BaseApi.RESOURCE_CACHE.get(cache_key)

        if result is None:
            try:
                result = BaseApi.RESOURCE_CACHE[cache_key] = getattr(client, api_method)(**api_kwargs)
            except botocore.exceptions.BotoCoreError as e:
                eprint("error: failed to list resources on {}:\n{}".format(service, e))
                raise SystemExit(-1)

        return result

    RESOURCE_PATTERN = r"\b{}\b"
    def _get_generic_all_resources(self, service, region, account, api_method, api_attribute, api_inner_attribute=None, resource_converter=None, api_kwargs={}):
        """
        >>> from pprint import pprint
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(BaseApi):
        ...     pass
        >>> runtime = Runtime()

        >>> class Client:
        ...     def list_tables(self):
        ...         return {'TableNames': ["table-1", "table-2"]}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> pprint(runtime._get_generic_all_resources('dynamodb', 'us-east-1', 'some-account', 'list_tables', 'TableNames'))
        {'table-1': re.compile('\\\\btable\\\\-1\\\\b', re.IGNORECASE),
         'table-2': re.compile('\\\\btable\\\\-2\\\\b', re.IGNORECASE)}
        >>> mock.calls_for('Runtime._get_client')
        'dynamodb', 'us-east-1', 'some-account'

        >>> class Client:
        ...     def list_buckets(self):
        ...         return {'Buckets': [{'Name': "bucket-1"}, {'Name': "bucket-2"}]}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> pprint(runtime._get_generic_all_resources('s3', 'us-east-1', 'some-account', 'list_buckets', 'Buckets', 'Name'))
        {'bucket-1': re.compile('\\\\bbucket\\\\-1\\\\b', re.IGNORECASE),
         'bucket-2': re.compile('\\\\bbucket\\\\-2\\\\b', re.IGNORECASE)}
        >>> mock.calls_for('Runtime._get_client')
        's3', 'us-east-1', 'some-account'

        >>> class Client:
        ...     def list_topics(self):
        ...         return {'Topics': [{'TopicArn': "arn:aws:sns:us-east-1:123456789012:my_topic"}]}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> pprint(runtime._get_generic_all_resources('sns', 'us-east-1', 'some-account', 'list_topics', 'Topics', 'TopicArn',
        ...                                           resource_converter=lambda topic_arn: BaseApi.ARN_RESOURCE_PATTERN.match(topic_arn).group(1)))
        {'my_topic': re.compile('\\\\bmy_topic\\\\b', re.IGNORECASE)}
        >>> mock.calls_for('Runtime._get_client')
        'sns', 'us-east-1', 'some-account'

        >>> mock.mock(None, 'eprint')

        >>> class Client:
        ...     def list_tables(self):
        ...         return {'TableNames': []}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> runtime._get_generic_all_resources('dynamodb', 'us-east-1', 'some-account', 'list_tables', 'TableNames')
        {}
        >>> mock.calls_for('eprint')
        "warn: no dynamodb resources on 'us-east-1:some-account': list_tables()"
        >>> mock.calls_for('Runtime._get_client')
        'dynamodb', 'us-east-1', 'some-account'

        >>> class Client:
        ...     def list_tables(self):
        ...         raise botocore.exceptions.NoCredentialsError()
        >>> mock.mock(runtime, '_get_client', Client())

        >>> runtime._get_generic_all_resources('dynamodb', 'us-east-1', 'some-account', 'list_tables', 'TableNames')
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: failed to list resources on dynamodb:\\nUnable to locate credentials'
        >>> mock.calls_for('Runtime._get_client')
        'dynamodb', 'us-east-1', 'some-account'
        """

        resources = self._get_cached_api_result(service, region=region, account=account, api_method=api_method, api_kwargs=api_kwargs)[api_attribute]
        if not resources:
            if not hasattr(self, '_no_resources_warnings'):
                self._no_resources_warnings = set()
            warning_arguments = (service, region, account, api_method, frozenset(api_kwargs.items()))
            if warning_arguments not in self._no_resources_warnings:
                eprint("warn: no {} resources on '{}:{}': {}({})".format(service, region, account, api_method, api_kwargs or ''))
                self._no_resources_warnings.add(warning_arguments)

        if api_inner_attribute:
            resources = (resource[api_inner_attribute] for resource in resources)
        if resource_converter:
            resources = (resource_converter(resource) for resource in resources)

        resources = dict(
                (resource, re.compile(BaseApi.RESOURCE_PATTERN.format(re.escape(resource)), re.IGNORECASE))
                for resource in resources
                )

        return resources

    def _get_generic_resources(self, filename, file, resources, region, account, resource_format, get_all_resources_method):
        """ Simply greps resources inside the given file.

        >>> from collections import defaultdict
        >>> from pprint import pprint
        >>> from io import StringIO
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(BaseApi):
        ...     pass
        >>> runtime = Runtime()
        >>> runtime.environment = {'var1': "gigi table-1 latable-6", 'var2': "table-2 table-3"}

        >>> class Client:
        ...     def list_tables(self):
        ...         return {'TableNames': ["table-1", "table-2", "table-3", "table-4", "table-5", "table-6"]}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> resources = defaultdict(set)
        >>> runtime._get_generic_resources('filename', StringIO("lalala table-4 lululu table-5 table-6la table-7 nonono"), resources, region='us-east-1', account='some-account',
        ...                                resource_format="table/{}", get_all_resources_method=partial(runtime._get_generic_all_resources, 'dynamodb', api_method='list_tables', api_attribute='TableNames'))
        >>> pprint(resources)
        {'table/table-1': set(), 'table/table-2': set(), 'table/table-3': set(), 'table/table-4': set(), 'table/table-5': set()}
        >>> mock.calls_for('Runtime._get_client')
        'dynamodb', 'us-east-1', 'some-account'
        """

        all_resources = get_all_resources_method(region=region, account=account)
        # From file
        content = file.read()
        for resource, pattern in all_resources.items():
            if pattern.search(content):
                resources[resource_format.format(resource)] # accessing to initialize defaultdict

        # From environment
        for resource, pattern in all_resources.items():
            if any(pattern.search(value) for value in self.environment.values() if isinstance(value, str)):
                resources[resource_format.format(resource)] # accessing to initialize defaultdict

    def _get_states_resources(self, filename, file, resources, region, account):
        # According to: https://forums.aws.amazon.com/thread.jspa?messageID=755476

        # state machines
        self._get_generic_resources(filename, file, resources, region=region, account=account, resource_format="stateMachine:{}",
                                    get_all_resources_method=partial(self._get_generic_all_resources, 'stepfunctions', api_method='list_state_machines', api_attribute='stateMachines', api_inner_attribute='name'))
        # activities
        self._get_generic_resources(filename, file, resources, region=region, account=account, resource_format="activity:{}",
                                    get_all_resources_method=partial(self._get_generic_all_resources, 'stepfunctions', api_method='list_activities', api_attribute='activities', api_inner_attribute='name'))
        # executions
        for state_machine in self._get_cached_api_result('stepfunctions', region=region, account=account, api_method='list_state_machines', api_kwargs={})['stateMachines']:
            self._get_generic_resources(filename, file, resources, region=region, account=account, resource_format="execution:{}:{{}}".format(state_machine['name']),
                                        get_all_resources_method=partial(self._get_generic_all_resources, 'stepfunctions', api_method='list_executions', api_attribute='executions', api_inner_attribute='name', api_kwargs={'stateMachineArn': state_machine['stateMachineArn']}))

    # { (service, region, account): client }
    CLIENTS_CACHE = {}
    def _get_client(self, service, region, account):
        """
        >>> from pprint import pprint
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Session:
        ...     def client(self, *args, **kwargs):
        ...         return (args, kwargs)
        >>> class Runtime(BaseApi):
        ...     pass
        >>> runtime = Runtime()
        >>> runtime.config = {}
        >>> runtime.session = Session()
        >>> runtime.default_account = 'default_account'

        >>> pprint(runtime._get_client('dynamodb', 'us-east-1', 'default_account'))
        (('dynamodb',), {'region_name': 'us-east-1'})

        >>> mock.mock(None, 'eprint')
        >>> pprint(runtime._get_client('dynamodb', 'us-east-1', '*'))
        (('dynamodb',), {'region_name': 'us-east-1'})
        >>> mock.calls_for('eprint')
        "warn: unknown account ('*'), using default session"

        >>> class Session:
        ...     def client(self, *args, **kwargs):
        ...         return (args, kwargs)
        >>> mock.mock(boto3, 'Session', Session())
        >>> mock.mock(None, 'input', lambda message: 'dummy')
        >>> pprint(runtime._get_client('dynamodb', 'us-east-1', 'another_account'))
        (('dynamodb',), {'region_name': 'us-east-1'})
        >>> mock.calls_for('boto3.Session')
        profile_name='dummy'
        >>> pprint(runtime.config)
        {'aws': {'accounts': {'another_account': {'profile': 'dummy'}}}}
        """
        client = BaseApi.CLIENTS_CACHE.get((service, region, account))
        if client:
            return client # from cache

        if region == '*':
            return None

        if account == '*':
            eprint("warn: unknown account ('*'), using default session")
            client = self.session.client(
                    service,
                    region_name=region
                    )
        elif account == self.default_account:
            client = self.session.client(
                    service,
                    region_name=region
                    )
        else:
            account_config = self.config.setdefault('aws', {}).setdefault('accounts', {}).setdefault(account, {})
            if not 'profile' in account_config:
                account_config['profile'] = input("Enter configured AWS profile for {}: ".format(account))
            client = boto3.Session(profile_name=account_config['profile']).client(service, region_name=region)

        BaseApi.CLIENTS_CACHE[(service, region, account)] = client
        return client

