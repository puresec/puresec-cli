""" Methods for AWS API. """

from puresec_cli.utils import eprint
import boto3
import botocore
import re

class AwsApi:
    CONFIGURATION_PROCESSORS = [
        # function(self, name, resource_id, resource_config)
        lambda self: self._process_logs_configuration,
        lambda self: self._process_vpc_configuration,
        lambda self: self._process_stream_configuration,
    ]

    def _process_logs_configuration(self, name, resource_id, resource_config):
        """
        >>> from pprint import pprint
        >>> provider = AwsApi()
        >>> provider.default_region = 'us-east-1'
        >>> provider.default_account = '1234'
        >>> provider._function_permissions = {}

        >>> provider._process_logs_configuration('someFunction', 'SomeFunctionName', {'Properties': {'FunctionName': 'SomeFunction'}})
        >>> pprint(provider._function_permissions)
        {'someFunction': {'arn:aws:logs:us-east-1:1234:log-group:/aws/lambda/SomeFunction': {'logs:CreateLogGroup'},
                          'arn:aws:logs:us-east-1:1234:log-group:/aws/lambda/SomeFunction:*': {'logs:CreateLogStream'},
                          'arn:aws:logs:us-east-1:1234:log-group:/aws/lambda/SomeFunction:*/*': {'logs:PutLogEvents'}}}
        """

        self._function_permissions. \
            setdefault(name, {}).   \
            setdefault("arn:aws:logs:{}:{}:log-group:/aws/lambda/{}".format(self.default_region, self.default_account, resource_config['Properties']['FunctionName']), set()). \
            add('logs:CreateLogGroup')

        self._function_permissions. \
            setdefault(name, {}).   \
            setdefault("arn:aws:logs:{}:{}:log-group:/aws/lambda/{}:*".format(self.default_region, self.default_account, resource_config['Properties']['FunctionName']), set()). \
            add('logs:CreateLogStream')

        self._function_permissions. \
            setdefault(name, {}).   \
            setdefault("arn:aws:logs:{}:{}:log-group:/aws/lambda/{}:*/*".format(self.default_region, self.default_account, resource_config['Properties']['FunctionName']), set()). \
            add('logs:PutLogEvents')

    VPC_ACTIONS = (
        'ec2:DescribeNetworkInterfaces',
        'ec2:CreateNetworkInterface',
        'ec2:DeleteNetworkInterface',
    )
    def _process_vpc_configuration(self, name, resource_id, resource_config):
        """
        >>> from tests.utils import normalize_dict
        >>> provider = AwsApi()
        >>> provider._function_permissions = {}

        >>> provider._process_vpc_configuration('someFunction', 'SomeFunctionName', {'Properties': {}})
        >>> provider._function_permissions
        {}
        >>> provider._process_vpc_configuration('someFunction', 'SomeFunctionName', {'Properties': {'VpcConfig': {}}})
        >>> normalize_dict(provider._function_permissions)
        {'someFunction': {'*': {'ec2:CreateNetworkInterface', 'ec2:DeleteNetworkInterface', 'ec2:DescribeNetworkInterfaces'}}}
        """

        if 'VpcConfig' not in resource_config['Properties']:
            return

        self._function_permissions. \
            setdefault(name, {}).   \
            setdefault('*', set()). \
            update(AwsApi.VPC_ACTIONS)

    # arn:aws:(kinesis):us-east-1:<account>:stream/<stream name>
    STREAM_ARN_SERVICE_PATTERN = re.compile(r"^arn:aws:([^:]*):[^:]*:[^:]*:stream/.*")
    STREAM_ACTIONS = (
        'DescribeStream',
        'GetRecords',
        'GetShardIterator',
        'ListStreams',
    )
    FUNCTION_ID_PATTERN = r"\b({}|{})\b"
    def _process_stream_configuration(self, name, resource_id, resource_config):
        """
        >>> from tests.utils import normalize_dict
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)

        >>> provider = AwsApi()
        >>> provider.default_region = 'us-east-1'
        >>> provider.default_account = '1234'
        >>> mock.mock(provider, 'get_cached_api_result', {'EventSourceMappings': []})

        >>> provider.cloudformation_template = {'Resources': {'Mapping': {'Type': 'AWS::Lambda::EventSourceMapping',
        ...                                                               'Properties': {'FunctionName': 'SomeFunction',
        ...                                                                              'EventSourceArn': 'arn:aws:kinesis:us-east-1:1234:stream/SomeStream'}}}}
        >>> provider._function_permissions = {}
        >>> provider._process_stream_configuration('functionName', 'SomeFunctionName', {'Properties': {'FunctionName': 'SomeFunction'}})
        >>> normalize_dict(provider._function_permissions)
        {'functionName': {'arn:aws:kinesis:us-east-1:1234:stream/SomeStream': {'kinesis:DescribeStream', 'kinesis:GetRecords', 'kinesis:GetShardIterator', 'kinesis:ListStreams'}}}
        >>> mock.calls_for('AwsApi.get_cached_api_result')
        'lambda', account='1234', api_kwargs={'FunctionName': 'SomeFunction'}, api_method='list_event_source_mappings', region='us-east-1'

        >>> provider.cloudformation_template = {'Resources': {'Mapping': {'Type': 'AWS::Lambda::EventSourceMapping',
        ...                                                               'Properties': {'FunctionName': 'arn:aws:lambda:us-east-1:1234:function:SomeFunction',
        ...                                                                              'EventSourceArn': 'arn:aws:kinesis:us-east-1:1234:stream/SomeStream'}}}}
        >>> provider._function_permissions = {}
        >>> provider._process_stream_configuration('functionName', 'SomeFunctionName', {'Properties': {'FunctionName': 'SomeFunction'}})
        >>> normalize_dict(provider._function_permissions)
        {'functionName': {'arn:aws:kinesis:us-east-1:1234:stream/SomeStream': {'kinesis:DescribeStream', 'kinesis:GetRecords', 'kinesis:GetShardIterator', 'kinesis:ListStreams'}}}
        >>> mock.calls_for('AwsApi.get_cached_api_result')
        'lambda', account='1234', api_kwargs={'FunctionName': 'SomeFunction'}, api_method='list_event_source_mappings', region='us-east-1'

        >>> provider.cloudformation_template = {'Resources': {'Mapping': {'Type': 'AWS::Lambda::EventSourceMapping',
        ...                                                               'Properties': {'FunctionName': 'AnotherFunction',
        ...                                                                              'EventSourceArn': 'arn:aws:kinesis:us-east-1:1234:stream/SomeStream'}}}}
        >>> provider._function_permissions = {}
        >>> provider._process_stream_configuration('functionName', 'SomeFunctionName', {'Properties': {'FunctionName': 'SomeFunction'}})
        >>> provider._function_permissions
        {}
        >>> mock.calls_for('AwsApi.get_cached_api_result')
        'lambda', account='1234', api_kwargs={'FunctionName': 'SomeFunction'}, api_method='list_event_source_mappings', region='us-east-1'

        >>> provider.cloudformation_template = {'Resources': {'Mapping': {'Type': 'AWS::Lambda::EventSourceMapping',
        ...                                                               'Properties': {'FunctionName': 'SomeFunction',
        ...                                                                              'EventSourceArn': 'arn:aws:dynamodb:us-east-1:1234:table/SomeTable'}}}}
        >>> provider._function_permissions = {}
        >>> provider._process_stream_configuration('functionName', 'SomeFunctionName', {'Properties': {'FunctionName': 'SomeFunction'}})
        >>> provider._function_permissions
        {}
        >>> mock.calls_for('AwsApi.get_cached_api_result')
        'lambda', account='1234', api_kwargs={'FunctionName': 'SomeFunction'}, api_method='list_event_source_mappings', region='us-east-1'

        >>> provider.cloudformation_template = {'Resources': {'Mapping': {'Type': 'AWS::DynamoDB::Table'}}}
        >>> provider._function_permissions = {}
        >>> provider._process_stream_configuration('functionName', 'SomeFunctionName', {'Properties': {'FunctionName': 'SomeFunction'}})
        >>> provider._function_permissions
        {}
        >>> mock.calls_for('AwsApi.get_cached_api_result')
        'lambda', account='1234', api_kwargs={'FunctionName': 'SomeFunction'}, api_method='list_event_source_mappings', region='us-east-1'

        >>> provider.cloudformation_template = None

        >>> mock.mock(provider, 'get_cached_api_result', {'EventSourceMappings': [{'EventSourceArn': 'arn:aws:kinesis:us-east-1:1234:stream/SomeStream'}]})
        >>> provider._function_permissions = {}
        >>> provider._process_stream_configuration('functionName', 'SomeFunctionName', {'Properties': {'FunctionName': 'SomeFunction'}})
        >>> normalize_dict(provider._function_permissions)
        {'functionName': {'arn:aws:kinesis:us-east-1:1234:stream/SomeStream': {'kinesis:DescribeStream', 'kinesis:GetRecords', 'kinesis:GetShardIterator', 'kinesis:ListStreams'}}}
        >>> mock.calls_for('AwsApi.get_cached_api_result')
        'lambda', account='1234', api_kwargs={'FunctionName': 'SomeFunction'}, api_method='list_event_source_mappings', region='us-east-1'

        >>> mock.mock(provider, 'get_cached_api_result', {'EventSourceMappings': [{'EventSourceArn': 'arn:aws:dynamodb:us-east-1:1234:table/SomeTable'}]})
        >>> provider._function_permissions = {}
        >>> provider._process_stream_configuration('functionName', 'SomeFunctionName', {'Properties': {'FunctionName': 'SomeFunction'}})
        >>> provider._function_permissions
        {}
        >>> mock.calls_for('AwsApi.get_cached_api_result')
        'lambda', account='1234', api_kwargs={'FunctionName': 'SomeFunction'}, api_method='list_event_source_mappings', region='us-east-1'
        """

        function_name = resource_config['Properties']['FunctionName']
        # From CloudFormation
        if self.cloudformation_template:
            function_id_pattern = re.compile(AwsApi.FUNCTION_ID_PATTERN.format(function_name, resource_id), re.IGNORECASE)
            for other_resource_id, other_resource_config in self.cloudformation_template.get('Resources', {}).items():
                if other_resource_config.get('Type') == 'AWS::Lambda::EventSourceMapping':
                    # either ARN, function name, or broken intrinsic function
                    target = other_resource_config.get('Properties', {}).get('FunctionName')
                    if target and function_id_pattern.search(target):
                        arn = other_resource_config['Properties'].get('EventSourceArn')
                        if not arn:
                            eprint("warn: event source mapping for `{}` missing `EventSourceArn`", name)
                            continue

                        service_match = AwsApi.STREAM_ARN_SERVICE_PATTERN.match(arn)
                        if not service_match:
                            continue
                        service = service_match.group(1)

                        self._function_permissions. \
                            setdefault(name, {}).   \
                            setdefault(arn, set()). \
                            update("{}:{}".format(service, action) for action in AwsApi.STREAM_ACTIONS)

        # From production environment
        event_source_mappings = self.get_cached_api_result('lambda', region=self.default_region, account=self.default_account, api_method='list_event_source_mappings', api_kwargs={'FunctionName': function_name})
        for event_source_mapping in event_source_mappings['EventSourceMappings']:
            service_match = AwsApi.STREAM_ARN_SERVICE_PATTERN.match(event_source_mapping['EventSourceArn'])
            if not service_match:
                continue
            service = service_match.group(1)

            self._function_permissions. \
                setdefault(name, {}).   \
                setdefault(event_source_mapping['EventSourceArn'], set()). \
                update("{}:{}".format(service, action) for action in AwsApi.STREAM_ACTIONS)

    # Utilities

    # { (client, api_method, api_kwargs): { resource: resource_pattern } } }
    RESOURCE_CACHE = {}
    def get_cached_api_result(self, service, region, account, api_method, api_kwargs={}):
        client = self.get_client(service, region, account)
        if client is None:
            eprint("error: cannot create {} client for region: '{}', account: '{}'", service, region, account)
            return

        cache_key = (client, api_method, frozenset(api_kwargs.items()))

        result = AwsApi.RESOURCE_CACHE.get(cache_key)

        if result is None:
            try:
                result = AwsApi.RESOURCE_CACHE[cache_key] = getattr(client, api_method)(**api_kwargs)
            except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
                eprint("error: failed to list resources on {}:\n{}", service, e)
                raise SystemExit(-1)

        return result

    # { (service, region, account): client }
    CLIENTS_CACHE = {}
    def get_client(self, service, region, account):
        """
        >>> from pprint import pprint
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Session:
        ...     def client(self, *args, **kwargs):
        ...         return (args, kwargs)
        >>> provider = AwsApi()
        >>> provider.config = {}
        >>> provider.session = Session()
        >>> provider.default_account = 'default_account'

        >>> pprint(provider.get_client('dynamodb', 'us-east-1', 'default_account'))
        (('dynamodb',), {'region_name': 'us-east-1'})

        >>> mock.mock(None, 'eprint')
        >>> pprint(provider.get_client('dynamodb', 'us-east-1', '*'))
        (('dynamodb',), {'region_name': 'us-east-1'})
        >>> mock.calls_for('eprint')
        "warn: unknown account ('*'), using default session"

        >>> class Session:
        ...     def client(self, *args, **kwargs):
        ...         return (args, kwargs)
        >>> mock.mock(boto3, 'Session', Session())
        >>> mock.mock(None, 'input', lambda message: 'dummy')
        >>> pprint(provider.get_client('dynamodb', 'us-east-1', 'another_account'))
        (('dynamodb',), {'region_name': 'us-east-1'})
        >>> mock.calls_for('boto3.Session')
        profile_name='dummy'
        >>> pprint(provider.config)
        {'aws': {'accounts': {'another_account': {'profile': 'dummy'}}}}
        """

        client = AwsApi.CLIENTS_CACHE.get((service, region, account))
        if client:
            return client # from cache

        if region == '*':
            eprint("warn: unknown region ('*'), using the default ('{}')", self.default_region)
            region = self.default_region

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

        AwsApi.CLIENTS_CACHE[(service, region, account)] = client
        return client

