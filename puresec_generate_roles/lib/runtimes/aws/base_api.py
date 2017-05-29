from functools import partial
import abc
import boto3
import botocore
import re

class BaseApi:
    __metaclass__ = abc.ABCMeta

    SERVICE_RESOURCES_PROCESSOR = {
            # service: function(self, filename, file, resources, region, account)
            'dynamodb': lambda self: partial(self._get_generic_resources, 'dynamodb', resource_format="table/{}",
                                             get_all_resources_method=partial(self._get_generic_all_resources, 'dynamodb', api_method='list_tables', api_attribute='TableNames')),
            'kinesis':  lambda self: partial(self._get_generic_resources, 'kinesis', resource_format="stream/{}",
                                             get_all_resources_method=partial(self._get_generic_all_resources, 'kinesis', api_method='list_streams', api_attribute='StreamNames')),
            's3':       lambda self: self._get_s3_resources,
            }

    # { client: { resource: resource_pattern } }
    RESOURCE_CACHE = {}
    RESOURCE_PATTERN = r"\b{}\b"
    def _get_generic_all_resources(self, service, region, account, api_method, api_attribute):
        """
        >>> from pprint import pprint
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(BaseApi):
        ...     pass
        >>> runtime = Runtime()
        >>> runtime.environment = {}

        >>> class Client:
        ...     def list_tables(self):
        ...         return {'TableNames': ["table-1", "table-2"]}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> pprint(runtime._get_generic_all_resources('dynamodb', 'us-east-1', 'some-account', 'list_tables', 'TableNames'))
        {'table-1': re.compile('\\\\btable\\\\-1\\\\b', re.IGNORECASE),
         'table-2': re.compile('\\\\btable\\\\-2\\\\b', re.IGNORECASE)}
        >>> mock.calls_for('Runtime._get_client')
        'dynamodb', 'us-east-1', 'some-account'

        >>> mock.mock(None, 'eprint')

        >>> class Client:
        ...     def list_tables(self):
        ...         return {'TableNames': []}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> runtime._get_generic_all_resources('dynamodb', 'us-east-1', 'some-account', 'list_tables', 'TableNames')
        {}
        >>> mock.calls_for('eprint')
        "warn: no resources on dynamodb on region 'us-east-1'"
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

        client = self._get_client(service, region, account)
        if client is None:
            eprint("error: cannot create {} client for region: '{}', account: '{}'".format(service, region, account))
            return

        resources = BaseApi.RESOURCE_CACHE.get(client)

        if resources is None:
            try:
                resources = getattr(client, api_method)()[api_attribute]
            except botocore.exceptions.BotoCoreError as e:
                eprint("error: failed to list resources on {}:\n{}".format(service, e))
                raise SystemExit(-1)
            resources = BaseApi.RESOURCE_CACHE[client] = dict(
                    (resource, re.compile(BaseApi.RESOURCE_PATTERN.format(re.escape(resource)), re.IGNORECASE))
                    for resource in resources
                    )
            if not resources:
                eprint("warn: no resources on {} on region '{}'".format(service, region))

        return resources

    def _get_generic_resources(self, service, filename, file, resources, region, account, resource_format, get_all_resources_method):
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
        >>> runtime._get_generic_resources('dynamodb', 'filename', StringIO("lalala table-4 lululu table-5 table-6la table-7 nonono"), resources, region='us-east-1', account='some-account',
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
        # From environment (TODO: once enough for entire lambda)
        if not hasattr(self, '_environment_resources'):
            self._environment_resources = {}
        if service not in self._environment_resources:
            self._environment_resources[service] = [
                    resource_format.format(resource)
                    for resource, pattern in all_resources.items()
                    if any(pattern.search(value) for value in self.environment.values() if isinstance(value, str))
                    ]
        for resource in self._environment_resources[service]:
            resources[resource] # accessing to initialize defaultdict

    # { client: { bucket: bucket_pattern } }
    S3_BUCKETS_CACHE = {}
    S3_BUCKET_PATTERN = r"\b{}\b"
    def _get_all_s3_buckets(self, region, account):
        """
        >>> from pprint import pprint
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(BaseApi):
        ...     pass
        >>> runtime = Runtime()
        >>> runtime.environment = {}

        >>> class Client:
        ...     def list_buckets(self):
        ...         return {'Buckets': [{'Name': "bucket-1"}, {'Name': "bucket-2"}]}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> pprint(runtime._get_all_s3_buckets('us-east-1', 'some-account'))
        {'bucket-1': re.compile('\\\\bbucket\\\\-1\\\\b', re.IGNORECASE),
         'bucket-2': re.compile('\\\\bbucket\\\\-2\\\\b', re.IGNORECASE)}
        >>> mock.calls_for('Runtime._get_client')
        's3', 'us-east-1', 'some-account'

        >>> mock.mock(None, 'eprint')

        >>> class Client:
        ...     def list_buckets(self):
        ...         return {'Buckets': []}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> runtime._get_all_s3_buckets('us-east-1', 'some-account')
        {}
        >>> mock.calls_for('eprint')
        "warn: no buckets on S3 on region 'us-east-1'"
        >>> mock.calls_for('Runtime._get_client')
        's3', 'us-east-1', 'some-account'

        >>> class Client:
        ...     def list_buckets(self):
        ...         raise botocore.exceptions.NoCredentialsError()
        >>> mock.mock(runtime, '_get_client', Client())

        >>> runtime._get_all_s3_buckets('us-east-1', 'some-account')
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: failed to list bucket names on S3:\\nUnable to locate credentials'
        >>> mock.calls_for('Runtime._get_client')
        's3', 'us-east-1', 'some-account'
        """

        client = self._get_client('s3', region, account)
        if client is None:
            eprint("error: cannot create S3 client for region: '{}', account: '{}'".format(region, account))
            return

        buckets = BaseApi.S3_BUCKETS_CACHE.get(client)

        if buckets is None:
            try:
                buckets = (bucket['Name'] for bucket in client.list_buckets()['Buckets'])
            except botocore.exceptions.BotoCoreError as e:
                eprint("error: failed to list bucket names on S3:\n{}".format(e))
                raise SystemExit(-1)
            buckets = BaseApi.S3_BUCKETS_CACHE[client] = dict(
                    (bucket, re.compile(BaseApi.S3_BUCKET_PATTERN.format(re.escape(bucket)), re.IGNORECASE))
                    for bucket in buckets
                    )
            if not buckets:
                eprint("warn: no buckets on S3 on region '{}'".format(region))

        return buckets

    S3_BUCKET_RESOURCE_FORMAT = "{}/*"
    def _get_s3_resources(self, filename, file, resources, region, account):
        """ Simply greps buckets inside the given file.

        >>> from collections import defaultdict
        >>> from pprint import pprint
        >>> from io import StringIO
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(BaseApi):
        ...     pass
        >>> runtime = Runtime()
        >>> runtime.environment = {'var1': "gigi bucket-1 labucket-6", 'var2': "bucket-2 bucket-3"}

        >>> class Client:
        ...     def list_buckets(self):
        ...         return {'Buckets': [{'Name': "bucket-1"}, {'Name': "bucket-2"}, {'Name': "bucket-3"},
        ...                             {'Name': "bucket-4"}, {'Name': "bucket-5"}, {'Name': "bucket-6"}]}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> resources = defaultdict(set)
        >>> runtime._get_s3_resources('filename', StringIO("lalala bucket-4 lululu bucket-5 bucket-6la bucket-7 nonono"), resources, region='us-east-1', account='some-account')
        >>> pprint(resources)
        {'bucket-1/*': set(), 'bucket-2/*': set(), 'bucket-3/*': set(), 'bucket-4/*': set(), 'bucket-5/*': set()}
        >>> mock.calls_for('Runtime._get_client')
        's3', 'us-east-1', 'some-account'
        """

        all_buckets = self._get_all_s3_buckets(region, account)
        # From file
        content = file.read()
        for bucket, pattern in all_buckets.items():
            if pattern.search(content):
                resources[BaseApi.S3_BUCKET_RESOURCE_FORMAT.format(bucket)] # accessing to initialize defaultdict
        # From environment (TODO: once enough for entire lambda)
        if not hasattr(self, '_environment_s3_resources'):
            self._environment_s3_resources = [
                    BaseApi.S3_BUCKET_RESOURCE_FORMAT.format(bucket)
                    for bucket, pattern in all_buckets.items()
                    if any(pattern.search(value) for value in self.environment.values() if isinstance(value, str))
                    ]
        for resource in self._environment_s3_resources:
            resources[resource] # accessing to initialize defaultdict

