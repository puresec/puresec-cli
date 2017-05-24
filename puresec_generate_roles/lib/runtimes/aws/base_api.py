import abc
import boto3
import botocore
import re

class BaseApi:
    __metaclass__ = abc.ABCMeta

    # { client: { table: table_pattern } }
    DYNAMODB_TABLES_CACHE = {}
    DYNAMODB_TABLE_PATTERN = r"\b{}\b"
    def _get_dynamodb_tables(self, region, account):
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

        >>> pprint(runtime._get_dynamodb_tables('us-east-1', 'some-account'))
        {'table-1': re.compile('\\\\btable\\\\-1\\\\b', re.IGNORECASE),
         'table-2': re.compile('\\\\btable\\\\-2\\\\b', re.IGNORECASE)}
        >>> mock.calls_for('Runtime._get_client')
        'dynamodb', 'us-east-1', 'some-account'

        >>> mock.mock(None, 'eprint')

        >>> class Client:
        ...     def list_tables(self):
        ...         return {'TableNames': []}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> runtime._get_dynamodb_tables('us-east-1', 'some-account')
        {}
        >>> mock.calls_for('eprint')
        "warn: no tables on DynamoDB on region 'us-east-1'"
        >>> mock.calls_for('Runtime._get_client')
        'dynamodb', 'us-east-1', 'some-account'

        >>> class Client:
        ...     def list_tables(self):
        ...         raise botocore.exceptions.NoCredentialsError()
        >>> mock.mock(runtime, '_get_client', Client())

        >>> runtime._get_dynamodb_tables('us-east-1', 'some-account')
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: failed to list table names on DynamoDB:\\nUnable to locate credentials'
        >>> mock.calls_for('Runtime._get_client')
        'dynamodb', 'us-east-1', 'some-account'
        """

        client = self._get_client('dynamodb', region, account)
        if client is None:
            eprint("error: cannot create DynamoDB client for region: '{}', account: '{}'".format(region, account))
            return

        tables = BaseApi.DYNAMODB_TABLES_CACHE.get(client)

        if tables is None:
            try:
                tables = client.list_tables()['TableNames']
            except botocore.exceptions.BotoCoreError as e:
                eprint("error: failed to list table names on DynamoDB:\n{}".format(e))
                raise SystemExit(-1)
            tables = BaseApi.DYNAMODB_TABLES_CACHE[client] = dict(
                    (table, re.compile(BaseApi.DYNAMODB_TABLE_PATTERN.format(re.escape(table)), re.IGNORECASE))
                    for table in tables
                    )
            if not tables:
                eprint("warn: no tables on DynamoDB on region '{}'".format(region))

        return tables

    DYNAMODB_TABLE_RESOURCE_FORMAT = "Table/{}"
    def _get_dynamodb_resources(self, filename, file, resources, region, account):
        """ Simply greps tables inside the given file.

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
        >>> runtime._get_dynamodb_resources('filename', StringIO("lalala table-4 lululu table-5 table-6la table-7 nonono"), resources, region='us-east-1', account='some-account')
        >>> pprint(resources)
        {'Table/table-1': set(), 'Table/table-2': set(), 'Table/table-3': set(), 'Table/table-4': set(), 'Table/table-5': set()}
        >>> mock.calls_for('Runtime._get_client')
        'dynamodb', 'us-east-1', 'some-account'
        """

        tables = self._get_dynamodb_tables(region, account)
        # From file
        content = file.read()
        for table, pattern in tables.items():
            if pattern.search(content):
                resources[BaseApi.DYNAMODB_TABLE_RESOURCE_FORMAT.format(table)] # accessing to initialize defaultdict
        # From environment (TODO: once enough for entire lambda)
        if not hasattr(self, '_environment_dynamodb_resources'):
            self._environment_dynamodb_resources = [
                    BaseApi.DYNAMODB_TABLE_RESOURCE_FORMAT.format(table)
                    for table, pattern in tables.items()
                    if any(pattern.search(value) for value in self.environment.values() if isinstance(value, str))
                    ]
        for resource in self._environment_dynamodb_resources:
            resources[resource] # accessing to initialize defaultdict

    # { client: { bucket: bucket_pattern } }
    S3_BUCKETS_CACHE = {}
    S3_BUCKET_PATTERN = r"\b{}\b"
    def _get_s3_buckets(self, region, account):
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

        >>> pprint(runtime._get_s3_buckets('us-east-1', 'some-account'))
        {'bucket-1': re.compile('\\\\bbucket\\\\-1\\\\b', re.IGNORECASE),
         'bucket-2': re.compile('\\\\bbucket\\\\-2\\\\b', re.IGNORECASE)}
        >>> mock.calls_for('Runtime._get_client')
        's3', 'us-east-1', 'some-account'

        >>> mock.mock(None, 'eprint')

        >>> class Client:
        ...     def list_buckets(self):
        ...         return {'Buckets': []}
        >>> mock.mock(runtime, '_get_client', Client())

        >>> runtime._get_s3_buckets('us-east-1', 'some-account')
        {}
        >>> mock.calls_for('eprint')
        "warn: no buckets on S3 on region 'us-east-1'"
        >>> mock.calls_for('Runtime._get_client')
        's3', 'us-east-1', 'some-account'

        >>> class Client:
        ...     def list_buckets(self):
        ...         raise botocore.exceptions.NoCredentialsError()
        >>> mock.mock(runtime, '_get_client', Client())

        >>> runtime._get_s3_buckets('us-east-1', 'some-account')
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

        buckets = self._get_s3_buckets(region, account)
        # From file
        content = file.read()
        for bucket, pattern in buckets.items():
            if pattern.search(content):
                resources[BaseApi.S3_BUCKET_RESOURCE_FORMAT.format(bucket)] # accessing to initialize defaultdict
        # From environment (TODO: once enough for entire lambda)
        if not hasattr(self, '_environment_s3_resources'):
            self._environment_s3_resources = [
                    BaseApi.S3_BUCKET_RESOURCE_FORMAT.format(bucket)
                    for bucket, pattern in buckets.items()
                    if any(pattern.search(value) for value in self.environment.values() if isinstance(value, str))
                    ]
        for resource in self._environment_s3_resources:
            resources[resource] # accessing to initialize defaultdict

