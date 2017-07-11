""" Methods for AWS API. """

from collections import defaultdict
from functools import partial
from puresec_cli.utils import eprint
import abc
import re

class BaseApi:
    __metaclass__ = abc.ABCMeta

    ARN_RESOURCE_PATTERN = re.compile(r"^arn:.*:(.+?)$")

    SERVICE_RESOURCES_PROCESSOR = {
        # service: function(self, filename, contents, resources, region, account)
        'dynamodb': lambda self: self._get_dynamodb_resources,
        'kinesis':  lambda self: partial(self._get_generic_resources, resource_format="stream/{}",
                                         get_all_resources_method=partial(self._get_generic_all_resources, 'kinesis', template_type='AWS::Kinesis::Stream', api_method='list_streams', api_attribute='StreamNames')),
        'kms':      lambda self: self._get_kms_resources,
        'lambda':   lambda self: partial(self._get_generic_resources, resource_format="{}",
                                         get_all_resources_method=partial(self._get_generic_all_resources, 'lambda', template_type='AWS::Lambda::Function', api_method='list_functions', api_attribute='Functions', api_inner_attribute='FunctionName')),
        's3':       lambda self: self._get_s3_resources,
        'sns':      lambda self: partial(self._get_generic_resources, resource_format="{}",
                                         get_all_resources_method=partial(self._get_generic_all_resources, 'sns', template_type='AWS::SNS::Topic', api_method='list_topics', api_attribute='Topics', api_inner_attribute='TopicArn',
                                                                          resource_converter=lambda topic_arn: BaseApi.ARN_RESOURCE_PATTERN.match(topic_arn).group(1))),
        'states':   lambda self: self._get_states_resources,
    }

    SERVICE_RESOURCE_ACTION_MATCHERS = {
        # service: (resource_pattern, resource_default, (action, ...))
        'dynamodb': (
            # stream
            (re.compile(r"table/.+/stream/.+"), "table/*/stream/*", set(
                "dynamodb:{}".format(action) for action in (
                    'DescribeStream', 'GetRecords', 'GetShardIterator',
                ))),
            # table
            (re.compile(r"table/.+"), "table/*", set(
                "dynamodb:{}".format(action) for action in (
                    'BatchGetItem', 'BatchWriteItem', 'CreateTable', 'DeleteItem', 'DeleteTable',
                    'DescribeTable', 'DescribeTimeToLive', 'GetItem', 'ListStreams', 'ListTagsOfResource',
                    'PutItem', 'Query', 'Scan', 'TagResource', 'UntagResource',
                    'UpdateItem', 'UpdateTable', 'UpdateTimeToLive',
                ))),
            # global
            (re.compile(r"\*$"), "*", set(
                "dynamodb:{}".format(action) for action in (
                    'DescribeLimits', 'DescribeReservedCapacity', 'DescribeReservedCapacityOfferings', 'ListTables', 'PurchaseReservedCapacityOfferings',
                ))),
        ),
        'kinesis': (
            # stream
            (re.compile(r"stream/.+"), "stream/*", set(
                "kinesis:{}".format(action) for action in (
                    'AddTagsToStream', 'DecreaseStreamRetentionPeriod', 'DeleteStream', 'DescribeLimits', 'DescribeStream',
                    'DisableEnhancedMonitoring', 'EnableEnhancedMonitoring', 'GetRecords', 'GetShardIterator', 'IncreaseStreamRetentionPeriod',
                    'ListTagsForStream', 'MergeShards', 'PutRecord', 'PutRecords', 'RemoveTagsFromStream',
                    'SplitShard', 'UpdateShardCount',
                ))),
            # global
            (re.compile(r"\*$"), "*", set(
                "kinesis:{}".format(action) for action in (
                    'CreateStream', 'ListStreams',
                ))),
        ),
        'kms': (
            # key
            (re.compile(r"key/.+"), "key/*", set(
                "kms:{}".format(action) for action in (
                    'CancelKeyDeletion', 'CreateAlias', 'CreateGrant', 'Decrypt', 'DeleteAlias',
                    'DeleteImportedKeyMaterial', 'DescribeKey', 'DisableKey', 'DisableKeyRotation', 'EnableKey',
                    'EnableKeyRotation', 'Encrypt', 'GenerateDataKey', 'GenerateDataKeyWithoutPlaintext', 'GetKeyPolicy',
                    'GetKeyRotationStatus', 'GetParametersForImport', 'ImportKeyMaterial', 'ListGrants', 'ListKeyPolicies',
                    'PutKeyPolicy', 'ReEncrypt', 'RevokeGrant', 'ScheduleKeyDeletion', 'UpdateAlias',
                    'UpdateKeyDescription',
                ))),
            # alias
            (re.compile(r"alias/.+"), "alias/*", set(
                "kms:{}".format(action) for action in (
                    'CreateAlias', 'DeleteAlias', 'UpdateAlias',
                ))),
            # global
            (re.compile(r"\*$"), "*", set(
                "kms:{}".format(action) for action in (
                    'CreateKey', 'GenerateRandom', 'ListAliases', 'ListKeys', 'ListRetirableGrants',
                ))),
        ),
    'lambda': (
        # function
        (re.compile(r".+"), "*", set(
            "lambda:{}".format(action) for action in (
                'AddPermission', 'CreateAlias', 'DeleteAlias', 'DeleteFunction', 'GetAccountSettings',
                'GetAlias', 'GetFunction', 'GetFunctionConfiguration', 'GetPolicy', 'InvokeAsync',
                'InvokeFunction', 'ListAliases', 'ListVersionsByFunction', 'PublishVersion', 'RemovePermission',
                'UpdateAlias', 'UpdateFunctionCode', 'UpdateFunctionConfiguration',
            ))),
        # global
        (re.compile(r"\*$"), "*", set(
            "lambda:{}".format(action) for action in (
                'CreateEventSourceMapping', 'CreateFunction', 'DeleteEventSourceMapping', 'GetEventSourceMapping', 'ListEventSourceMappings',
                'ListFunctions', 'UpdateEventSourceMapping',
            ))),
    ),
    's3': (
        # object
        (re.compile(r".+/.+"), "*/*", set(
            "s3:{}".format(action) for action in (
                'AbortMultipartUpload', 'DeleteObject', 'DeleteObjectTagging', 'GetObject', 'GetObjectAcl',
                'GetObjectTagging', 'GetObjectTorrent', 'ListMultipartUploadParts', 'PutObject', 'PutObjectAcl',
                'PutObjectTagging', 'RestoreObject',
            ))),
        # bucket
        (re.compile(r".+"), "*", set(
            "s3:{}".format(action) for action in (
                'DeleteBucket' 'DeleteBucketPolicy' 'DeleteBucketWebsite' 'DeleteReplicationConfiguration', 'GetAccelerateConfiguration',
                'GetAnalyticsConfiguration', 'GetBucketAcl', 'GetBucketCORS', 'GetBucketLocation' 'GetBucketLogging'
                'GetBucketNotification' 'GetBucketNotification', 'GetBucketPolicy' 'GetBucketRequestPayment', 'GetBucketTagging'
                'GetBucketVersioning' 'GetBucketWebsite' 'GetInventoryConfiguration', 'GetLifecycleConfiguration', 'GetMetricsConfiguration',
                'GetReplicationConfiguration', 'ListBucket', 'ListBucketMultipartUploads', 'ListBucketVersions', 'PutAccelerateConfiguration',
                'PutAnalyticsConfiguration', 'PutBucketAcl' 'PutBucketCORS', 'PutBucketLogging', 'PutBucketNotification'
                'PutBucketNotification', 'PutBucketPolicy' 'PutBucketRequestPayment' 'PutBucketTagging' 'PutBucketTagging',
                'PutBucketVersioning', 'PutBucketWebsite', 'PutInventoryConfiguration', 'PutLifecycleConfiguration', 'PutMetricsConfiguration',
                'PutReplicationConfiguration',
            ))),
        # global
        (re.compile(r"\*$"), "*", set(
            "s3:{}".format(action) for action in (
                'CreateBucket', 'ListAllMyBuckets',
            ))),
    ),
    'sns': (
        # function
        (re.compile(r".+"), "*", set(
            "sns:{}".format(action) for action in (
                'AddPermission', 'CheckIfPhoneNumberIsOptedOut', 'ConfirmSubscription', 'CreatePlatformApplication', 'CreatePlatformEndpoint',
                'DeleteEndpoint', 'DeletePlatformApplication', 'DeleteTopic', 'GetEndpointAttributes', 'GetPlatformApplicationAttributes',
                'GetSMSAttributes', 'GetSubscriptionAttributes', 'GetTopicAttributes', 'ListEndpointsByPlatformApplication', 'ListPhoneNumbersOptedOut',
                'ListPlatformApplications', 'ListSubscriptions', 'ListSubscriptionsByTopic', 'OptInPhoneNumber', 'Publish',
                'RemovePermission', 'SetEndpointAttributes', 'SetPlatformApplicationAttributes', 'SetSMSAttributes', 'SetSubscriptionAttributes',
                'SetTopicAttributes', 'Subscribe', 'Unsubscribe',
            ))),
        # global
        (re.compile(r"\*$"), "*", set(
            "sns:{}".format(action) for action in (
                'CreateTopic', 'ListTopics',
            ))),
    ),
    'states': (
        # state machine
        (re.compile(r"stateMachine:.+"), "stateMachine:*", set(
            "states:{}".format(action) for action in (
                'DeleteStateMachine', 'DescribeStateMachine', 'ListExecutions',
            ))),
        # activity
        (re.compile(r"activity:.+"), "activity:*", set(
            "states:{}".format(action) for action in (
                'DeleteActivity', 'DescribeActivity', 'GetActivityTask',
            ))),
        # execution
        (re.compile(r"execution:.+:.+"), "execution:*:*", set(
            "states:{}".format(action) for action in (
                'DescribeExecution', 'GetExecutionHistory', 'StartExecution', 'StopExecution',
            ))),
        # global
        (re.compile(r"\*$"), "*", set(
            "states:{}".format(action) for action in (
                'CreateActivity', 'CreateStateMachine', 'ListActivities', 'ListStateMachines', 'SendTaskFailure',
                'SendTaskHeartbeat', 'SendTaskSuccess',
            ))),
    ),
    }

    REGIONLESS_SERVICES = (
        's3',
    )

    SERVICE_RESOURCELESS_ACTIONS = {
        'dynamodb': tuple(
            # "CreateBucket" -> "s3:CreateBucket"
            "dynamodb:{}".format(action)
            for action in (
                    'DescribeLimits', 'DescribeReservedCapacity', 'DescribeReservedCapacityOfferings', 'ListTables', 'PurchaseReservedCapacityOfferings',
            )
        ),
        's3': tuple(
            "s3:{}".format(action)
            for action in (
                    'CreateBucket', 'ListAllMyBuckets',
            )
        ),
        'states': tuple(
            "states:{}".format(action)
            for action in (
                    'createActivity', 'createStateMachine', 'listActivities', 'listStateMachines', 'sendTaskFailure',
                    'sendTaskHeartbeat', 'sendTaskSuccess',
            )
        )
    }

    RESOURCE_PATTERN = r"\b{}\b"
    def _get_generic_all_resources(self, service, region, account, template_type, api_method, api_attribute, api_inner_attribute=None, resource_converter=None, api_kwargs={}, warn=True):
        """
        >>> from pprint import pprint
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(BaseApi):
        ...     pass
        >>> runtime = Runtime()

        >>> class Provider:
        ...     pass
        >>> runtime.provider = Provider()

        >>> mock.mock(runtime.provider, 'get_cached_api_result', {'TableNames': []})

        >>> runtime.provider.cloudformation_template = {'Resources': {'T1': {'Type': 'AWS::DynamoDB::Table', 'Properties': {'TableName': 'table-1'}},
        ...                                                           'T2': {'Type': 'AWS::DynamoDB::Table', 'Properties': {'TableName': 'table-2'}},
        ...                                                           'B1': {'Type': 'AWS::S3::Bucket', 'Properties': {'TableName': 'not-table-2'}}}}
        >>> pprint(runtime._get_generic_all_resources('dynamodb', 'us-east-1', 'some-account', 'AWS::DynamoDB::Table', 'list_tables', 'TableNames'))
        {'table-1': re.compile('\\\\btable\\\\-1\\\\b', re.IGNORECASE),
         'table-2': re.compile('\\\\btable\\\\-2\\\\b', re.IGNORECASE)}
        >>> mock.calls_for('Provider.get_cached_api_result')
        'dynamodb', account='some-account', api_kwargs={}, api_method='list_tables', region='us-east-1'

        >>> runtime.provider.cloudformation_template = None

        >>> mock.mock(runtime.provider, 'get_cached_api_result', {'TableNames': ['table-1', 'table-2']})

        >>> pprint(runtime._get_generic_all_resources('dynamodb', 'us-east-1', 'some-account', 'AWS::DynamoDB::Table', 'list_tables', 'TableNames'))
        {'table-1': re.compile('\\\\btable\\\\-1\\\\b', re.IGNORECASE),
         'table-2': re.compile('\\\\btable\\\\-2\\\\b', re.IGNORECASE)}
        >>> mock.calls_for('Provider.get_cached_api_result')
        'dynamodb', account='some-account', api_kwargs={}, api_method='list_tables', region='us-east-1'

        >>> mock.mock(runtime.provider, 'get_cached_api_result', {'Buckets': [{'Name': "bucket-1"}, {'Name': "bucket-2"}]})

        >>> pprint(runtime._get_generic_all_resources('s3', 'us-east-1', 'some-account', 'AWS::S3::Bucket', 'list_buckets', 'Buckets', 'Name'))
        {'bucket-1': re.compile('\\\\bbucket\\\\-1\\\\b', re.IGNORECASE),
         'bucket-2': re.compile('\\\\bbucket\\\\-2\\\\b', re.IGNORECASE)}
        >>> mock.calls_for('Provider.get_cached_api_result')
        's3', account='some-account', api_kwargs={}, api_method='list_buckets', region='us-east-1'

        >>> mock.mock(runtime.provider, 'get_cached_api_result', {'Topics': [{'TopicArn': "arn:aws:sns:us-east-1:123456789012:my_topic"}]})

        >>> pprint(runtime._get_generic_all_resources('sns', 'us-east-1', 'some-account', 'AWS::SNS::Topic', 'list_topics', 'Topics', 'TopicArn',
        ...                                           resource_converter=lambda topic_arn: BaseApi.ARN_RESOURCE_PATTERN.match(topic_arn).group(1)))
        {'my_topic': re.compile('\\\\bmy_topic\\\\b', re.IGNORECASE)}
        >>> mock.calls_for('Provider.get_cached_api_result')
        'sns', account='some-account', api_kwargs={}, api_method='list_topics', region='us-east-1'

        >>> mock.mock(None, 'eprint')

        >>> mock.mock(runtime.provider, 'get_cached_api_result', {'TableNames': []})

        >>> runtime._get_generic_all_resources('dynamodb', 'us-east-1', 'some-account', 'AWS::DynamoDB::Table', 'list_tables', 'TableNames')
        {}
        >>> mock.calls_for('eprint')
        "warn: no {} resources ({}) on '{}:{}', you're using this service but your AWS account and CloudFormation are empty", 'dynamodb', 'AWS::DynamoDB::Table', 'us-east-1', 'some-account'
        >>> mock.calls_for('Provider.get_cached_api_result')
        'dynamodb', account='some-account', api_kwargs={}, api_method='list_tables', region='us-east-1'
        """

        resources = {}

        if self.provider.cloudformation_template and template_type:
            name_attribute = "{}Name".format(template_type.split('::')[-1])
            for logical_id, properties in self.provider.cloudformation_template.get('Resources', {}).items():
                if properties.get('Type') == template_type:
                    resource = properties.get('Properties', {}).get(name_attribute)
                    if resource:
                        resources[resource] = re.compile(BaseApi.RESOURCE_PATTERN.format(re.escape(resource)), re.IGNORECASE)

        api_resources = self.provider.get_cached_api_result(service, region=region, account=account, api_method=api_method, api_kwargs=api_kwargs)[api_attribute]

        if api_inner_attribute:
            api_resources = (resource[api_inner_attribute] for resource in api_resources)
        if resource_converter:
            api_resources = (resource_converter(resource) for resource in api_resources)

        resources.update(
                (resource, re.compile(BaseApi.RESOURCE_PATTERN.format(re.escape(resource)), re.IGNORECASE))
                for resource in api_resources
                )

        if not resources and warn:
            if not hasattr(self, '_no_resources_warnings'):
                self._no_resources_warnings = set()
            warning_arguments = (service, template_type, region, account)
            if warning_arguments not in self._no_resources_warnings:
                eprint("warn: no {} resources ({}) on '{}:{}', you're using this service but your AWS account and CloudFormation are empty", *warning_arguments)
                self._no_resources_warnings.add(warning_arguments)
            return {}

        return resources

    def _get_s3_resources(self, filename, contents, resources, region, account):
        # buckets
        buckets = defaultdict(set)
        self._get_generic_resources(filename, contents, buckets, region=region, account=account, resource_format="{}",
                                    get_all_resources_method=partial(self._get_generic_all_resources, 's3', template_type='AWS::S3::Bucket', api_method='list_buckets', api_attribute='Buckets', api_inner_attribute='Name'))
        resources.update(buckets)
        # objects
        for bucket in buckets:
            resources["{}/*".format(bucket)]

    def _get_dynamodb_resources(self, filename, contents, resources, region, account):
        # tables
        tables = defaultdict(set)
        self._get_generic_resources(filename, contents, tables, region=region, account=account, resource_format="table/{}",
                                    get_all_resources_method=partial(self._get_generic_all_resources, 'dynamodb', template_type='AWS::DynamoDB::Table', api_method='list_tables', api_attribute='TableNames'))
        resources.update(tables)
        # streams
        for table in tables:
            if table.endswith('*'):
                resources["{}/streams/*".format(table)]
            else:
                table = re.sub(r"^table/", '', table)
                self._get_generic_resources(filename, contents, resources, region=region, account=account, resource_format="table/{}/stream/{{}}".format(table),
                                            get_all_resources_method=partial(self._get_generic_all_resources, 'dynamodbstreams', template_type=None, api_method='list_streams', api_attribute='Streams', api_inner_attribute='StreamLabel', api_kwargs={'TableName': table}, warn=False))

    def _get_kms_resources(self, filename, contents, resources, region, account):
        # keys
        self._get_generic_resources(filename, contents, resources, region=region, account=account, resource_format="key/{}",
                                    get_all_resources_method=partial(self._get_generic_all_resources, 'kms', template_type='AWS::KMS::Key', api_method='list_keys', api_attribute='Keys', api_inner_attribute='KeyId'))
        # aliases
        self._get_generic_resources(filename, contents, resources, region=region, account=account, resource_format="alias/{}",
                                    get_all_resources_method=partial(self._get_generic_all_resources, 'kms', template_type='AWS::KMS::Alias', api_method='list_aliases', api_attribute='Aliases', api_inner_attribute='AliasName'))

    def _get_states_resources(self, filename, contents, resources, region, account):
        # According to: https://forums.aws.amazon.com/thread.jspa?messageID=755476

        # state machines
        state_machines = defaultdict(set)
        self._get_generic_resources(filename, contents, state_machines, region=region, account=account, resource_format="stateMachine:{}",
                                    get_all_resources_method=partial(self._get_generic_all_resources, 'stepfunctions', template_type='AWS::StepFunctions::StateMachine', api_method='list_state_machines', api_attribute='stateMachines', api_inner_attribute='name'))
        resources.update(state_machines)
        # activities
        self._get_generic_resources(filename, contents, resources, region=region, account=account, resource_format="activity:{}",
                                    get_all_resources_method=partial(self._get_generic_all_resources, 'stepfunctions', template_type='AWS::StepFunctions::Activity', api_method='list_activities', api_attribute='activities', api_inner_attribute='name'))
        # executions
        state_machine_arns = dict(
                (state_machine['name'], state_machine['stateMachineArn'])
                for state_machine in
                self.provider.get_cached_api_result('stepfunctions', region=region, account=account, api_method='list_state_machines')['stateMachines']
                )
        for state_machine in state_machines:
            if state_machine.endswith('*'):
                resources["executions:*:*"]
            else:
                state_machine = re.sub(r"^stateMachine:", '', state_machine)
                self._get_generic_resources(filename, contents, resources, region=region, account=account, resource_format="execution:{}:{{}}".format(state_machine),
                                            get_all_resources_method=partial(self._get_generic_all_resources, 'stepfunctions', template_type=None, api_method='list_executions', api_attribute='executions', api_inner_attribute='name', api_kwargs={'stateMachineArn': state_machine_arns[state_machine]}))

