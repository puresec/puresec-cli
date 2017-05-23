from collections import defaultdict, namedtuple
from copy import deepcopy
from functools import reduce
from lib.runtimes.base import Base as RuntimeBase
from lib.utils import deepmerge, eprint
import abc
import boto3
import botocore
import re

class Base(RuntimeBase):
    __metaclass__ = abc.ABCMeta

    Permission = namedtuple('Permission', ('service', 'region', 'account', 'resource'))

    def __init__(self, root, config, session, default_region, default_account, environment):
        super().__init__(root, config)
        self.session = session
        self.default_region = default_region
        self.default_account = default_account
        self.environment = environment

        # { service: { region: { account: { resource } } } }
        self._permissions = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

    @property
    def permissions(self):
        """
        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account', environment={})
        >>> runtime._permissions = {
        ...     'dynamodb': {'us-west-1': {'111': {'Table/a', 'Table/b'}}},
        ...     'ses': {'*': {'111': {'*'}, '222': {'*'}}},
        ...     }

        >>> sorted(runtime.permissions)
        ['arn:aws:dynamodb:us-west-1:111:Table/a',
         'arn:aws:dynamodb:us-west-1:111:Table/b',
         'arn:aws:ses:*:111:*',
         'arn:aws:ses:*:222:*']
        """

        permissions = []
        for service, regions in self._permissions.items():
            for region, accounts in regions.items():
                for account, resources in accounts.items():
                    for resource in resources:
                        permissions.append("arn:aws:{}:{}:{}:{}".format(service, region, account, resource))
        return permissions

    def process(self):
        self._process_services()
        self._process_regions()
        self._process_resources()

    @abc.abstractmethod
    def _get_services(self, filename, file):
        pass

    try:
        REGION_PATTERNS = dict(
                (region, re.compile(r"\b{}\b".format(re.escape(region))))
                for region in boto3.Session().get_available_regions('ec2')
                )
    except botocore.exceptions.BotoCoreError as e:
        eprint("error: failed to create aws session:\n{}".format(e))
        raise SystemExit(-1)
    # regions = set()
    def _get_regions(self, filename, file, regions, service, account):
        """
        >>> from io import StringIO

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account',
        ...                 environment={ 'var1': "gigi eu-west-1 laus-east-2", 'var2': "eu-central-1 ca-central-1" })

        >>> regions = set()
        >>> runtime._get_regions('filename', StringIO("lalala us-east-1 lululu us-west-1 us-east-2la us-west-5 nonono"), regions, 'dynamodb', '*')
        >>> sorted(regions)
        ['ca-central-1', 'eu-central-1', 'eu-west-1', 'us-east-1', 'us-west-1']
        """

        # From file
        content = file.read()
        regions.update(
                region for region, pattern in Base.REGION_PATTERNS.items()
                if pattern.search(content)
                )
        # From environment
        if not hasattr(self, '_environment_regions'):
            self._environment_regions = set(
                    region for region, pattern in Base.REGION_PATTERNS.items()
                    if any(pattern.search(value) for value in self.environment.values() if isinstance(value, str))
                    )
        regions.update(self._environment_regions)

    # resources = set()
    @abc.abstractmethod
    def _get_resources(self, filename, file, resources, client, service):
        pass

    # { client: { table: table_pattern } }
    DYNAMODB_TABLES_CACHE = {}
    DYNAMODB_TABLE_PATTERN = r"\b{}\b"
    def _get_dynamodb_tables(self, client):
        """
        >>> from pprint import pprint
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account', environment={})

        >>> class Client:
        ...     def list_tables(self):
        ...         return {'TableNames': ["table-1", "table-2"]}

        >>> pprint(runtime._get_dynamodb_tables(Client()))
        {'table-1': re.compile('\\\\btable\\\\-1\\\\b', re.IGNORECASE),
         'table-2': re.compile('\\\\btable\\\\-2\\\\b', re.IGNORECASE)}

        >>> mock.mock(None, 'eprint')

        >>> class Client:
        ...     class meta:
        ...         region_name = 'eu-east-1'
        ...     def list_tables(self):
        ...         return {'TableNames': []}

        >>> runtime._get_dynamodb_tables(Client())
        {}
        >>> mock.calls_for('eprint')
        "warn: no tables on DynamoDB on region 'eu-east-1'"

        >>> class Client:
        ...     def list_tables(self):
        ...         raise botocore.exceptions.NoCredentialsError()

        >>> runtime._get_dynamodb_tables(Client())
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: failed to list table names on DynamoDB:\\nUnable to locate credentials'
        """

        tables = Base.DYNAMODB_TABLES_CACHE.get(client)

        if tables is None:
            try:
                tables = client.list_tables()['TableNames']
            except botocore.exceptions.BotoCoreError as e:
                eprint("error: failed to list table names on DynamoDB:\n{}".format(e))
                raise SystemExit(-1)
            tables = Base.DYNAMODB_TABLES_CACHE[client] = dict(
                    (table, re.compile(Base.DYNAMODB_TABLE_PATTERN.format(re.escape(table)), re.IGNORECASE))
                    for table in tables
                    )
            if not tables:
                eprint("warn: no tables on DynamoDB on region '{}'".format(client.meta.region_name))

        return tables

    DYNAMODB_TABLE_RESOURCE_FORMAT = "Table/{}"
    def _get_dynamodb_resources(self, filename, file, resources, client):
        """ Simply greps tables inside the given file.

        >>> from io import StringIO

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account',
        ...                 environment={ 'var1': "gigi table-1 latable-6", 'var2': "table-2 table-3" })

        >>> class Client:
        ...     def list_tables(self):
        ...         return {'TableNames': ["table-1", "table-2", "table-3", "table-4", "table-5", "table-6"]}

        >>> resources = set()
        >>> runtime._get_dynamodb_resources('filename', StringIO("lalala table-4 lululu table-5 table-6la table-7 nonono"), resources, Client())
        >>> sorted(resources)
        ['Table/table-1', 'Table/table-2', 'Table/table-3', 'Table/table-4', 'Table/table-5']
        """

        tables = self._get_dynamodb_tables(client)
        # From file
        content = file.read()
        resources.update(
                Base.DYNAMODB_TABLE_RESOURCE_FORMAT.format(table)
                for table, pattern in tables.items()
                if pattern.search(content)
                )
        # From environment (TODO: once enough for entire lambda)
        if not hasattr(self, '_environment_dynamodb_resources'):
            self._environment_dynamodb_resources = set(
                    Base.DYNAMODB_TABLE_RESOURCE_FORMAT.format(table)
                    for table, pattern in tables.items()
                    if any(pattern.search(value) for value in self.environment.values() if isinstance(value, str))
                    )
        resources.update(self._environment_dynamodb_resources)

    # Sub processors

    def _process_services(self):
        self._walk(self._get_services)
        self._normalize_permissions(self._permissions)

    def _process_regions(self):
        """ Expands '*' regions to all regions seen within the code.

        >>> from pprint import pprint
        >>> from test.utils import normalize_dict
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account', environment={})

        >>> mock.mock(Base, '_walk', lambda self, processor, possible_regions, service, account: possible_regions.update({'us-east-1', 'us-east-2'}))
        >>> runtime._permissions = {
        ...     'dynamodb': {'us-west-1': {'111': {'Table/a', 'Table/b'}}},
        ...     'ses': defaultdict(dict, {'*': {'111': {'*'}, '222': {'*'}}})
        ...     }
        >>> runtime._process_regions()
        >>> mock.calls_for('Base._walk')
        Runtime, _get_regions, {'us-east-1', 'us-east-2'}, account='111', service='ses'
        Runtime, _get_regions, {'us-east-1', 'us-east-2'}, account='222', service='ses'
        >>> pprint(normalize_dict(runtime._permissions))
        {'dynamodb': {'us-west-1': {'111': {'Table/a', 'Table/b'}}},
         'ses': {'us-east-1': {'111': {'*'}, '222': {'*'}}, 'us-east-2': {'111': {'*'}, '222': {'*'}}}}
        """

        for service, regions in self._permissions.items():
            if '*' in regions:
                for account, resources in sorted(regions['*'].items()):
                    possible_regions = set()
                    self._walk(
                            self._get_regions,
                            # custom arguments to processor
                            possible_regions,
                            service=service,
                            account=account
                            )
                    # moving the account from '*' to possible regions
                    if possible_regions:
                        for region in possible_regions:
                            regions[region][account] = deepcopy(resources)
                        del regions['*'][account]

                if not regions['*']:
                    # all moved
                    del regions['*']

    def _process_resources(self):
        for service, regions in self._permissions.items():
            for region, accounts in regions.items():
                for account, resources in accounts.items():
                    if region == '*' or account == '*':
                        resources.add('*')
                        continue
                    self._walk(
                            self._get_resources,
                            # custom arguments to processor
                            resources,
                            client=self._get_client(service, region, account),
                            service=service,
                            )
                    self._normalize_resources(resources, (service, region, account))

    # Helpers

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
        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', config={}, session=Session(), default_region='default_region', default_account='default_account', environment={})

        >>> pprint(runtime._get_client('dynamodb', 'us-east-1', 'default_account'))
        (('dynamodb',), {'region_name': 'us-east-1'})

        >>> mock.mock(None, 'eprint')
        >>> pprint(runtime._get_client('dynamodb', 'us-east-1', '*'))
        (('dynamodb',), {'region_name': 'us-east-1'})
        >>> mock.calls_for('eprint')
        "warn: unknown account ('*'), using default session"

        >>> mock.mock(None, 'input', lambda message: 'dummy')
        >>> pprint(runtime._get_client('dynamodb', 'us-east-1', 'another_account'))
        (('dynamodb',), {'aws_access_key_id': 'dummy', 'aws_secret_access_key': 'dummy', 'region_name': 'us-east-1'})
        >>> pprint(runtime.config)
        {'aws': {'accounts': {'another_account': {'access_key_id': 'dummy', 'secret_access_key': 'dummy'}}}}
        """
        client = Base.CLIENTS_CACHE.get((service, region, account))
        if client:
            return client # from cache

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
            if not 'access_key_id' in account_config:
                account_config['access_key_id'] = input("Enter AWS access key id for {}: ".format(account))
                account_config['secret_access_key'] = input("Enter AWS secret access key for {}: ".format(account))
            client = self.session.client(
                    service,
                    region_name=region,
                    aws_access_key_id=account_config['access_key_id'],
                    aws_secret_access_key=account_config['secret_access_key']
                    )

        Base.CLIENTS_CACHE[(service, region, account)] = client
        return client

    def _normalize_permissions(self, tree):
        """ Merge trees when one of the keys have '*' permission.

        >>> from pprint import pprint
        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account', environment={})

        >>> tree = {'a': {'b': {'c': 1}, '*': {'d': 2}, 'e': {'f': 3}}}
        >>> runtime._normalize_permissions(tree)
        >>> pprint(tree)
        {'a': {'*': {'c': 1, 'd': 2, 'f': 3}}}

        >>> tree = {'b': {'c': 1}, '*': {'d': 2}, 'e': {'f': 3}}
        >>> runtime._normalize_permissions(tree)
        >>> pprint(tree)
        {'*': {'c': 1, 'd': 2, 'f': 3}}
        """

        if '*' in tree:
            merged = reduce(deepmerge, tree.values())
            tree.clear()
            tree['*'] = merged

        for k, v in tree.items():
            if isinstance(v, dict):
                self._normalize_permissions(v)

    MATCH_ALL_RESOURCES = ('*', '*/*', '*:*')
    def _normalize_resources(self, resources, parents):
        """ Convert set to match-all when there's at least one.

        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account', environment={})

        >>> resources = {'a', 'b', 'c'}
        >>> runtime._normalize_resources(resources, ['dynamodb', 'us-west-1'])
        >>> sorted(resources)
        ['a', 'b', 'c']

        >>> resources = {'a', '*/*', 'c'}
        >>> runtime._normalize_resources(resources, ['dynamodb', 'us-west-1'])
        >>> resources
        {'*/*'}

        >>> mock.mock(None, 'eprint')
        >>> resources = set()
        >>> runtime._normalize_resources(resources, ['dynamodb', 'us-west-1'])
        >>> mock.calls_for('eprint')
        "warn: unknown permissions for 'dynamodb:us-west-1'"
        >>> resources
        {'*'}

        """

        if not resources:
            resources.add('*')
            eprint("warn: unknown permissions for '{}'".format(':'.join(parents)))
        else:
            for match_all in Base.MATCH_ALL_RESOURCES:
                if match_all in resources:
                    resources.clear()
                    resources.add(match_all)
                    break

