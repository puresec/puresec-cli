from collections import defaultdict, namedtuple
from copy import deepcopy
from functools import reduce
from lib.runtimes.base import Base as RuntimeBase
from lib.runtimes.aws.base_api import BaseApi
from lib.utils import deepmerge, eprint
import abc
import boto3
import botocore
import re

class Base(RuntimeBase, BaseApi):
    __metaclass__ = abc.ABCMeta

    def __init__(self, root, config, session, default_region, default_account, environment):
        super().__init__(root, config)
        self.session = session
        self.default_region = default_region
        self.default_account = default_account
        self.environment = environment

        # { service: { region: { account: { resource: {action} } } } }
        self._permissions = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(set))))

    @property
    def permissions(self):
        """
        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account', environment={})
        >>> runtime._permissions = {
        ...     'dynamodb': {'us-west-1': {'111': {'Table/a': {'GetRecords'}, 'Table/b': {'UpdateItem'}}}},
        ...     'ses': {'*': {'111': {'*': {'*'}}, '222': {'*': {'*'}}}},
        ...     }

        >>> sorted(runtime.permissions)
        [('arn:aws:dynamodb:us-west-1:111:Table/a', {'GetRecords'}),
         ('arn:aws:dynamodb:us-west-1:111:Table/b', {'UpdateItem'}),
         ('arn:aws:ses:*:111:*', {'*'}),
         ('arn:aws:ses:*:222:*', {'*'})]
        """

        permissions = []
        for service, regions in self._permissions.items():
            for region, accounts in regions.items():
                for account, resources in accounts.items():
                    for resource, actions in resources.items():
                        permissions.append(("arn:aws:{}:{}:{}:{}".format(service, region, account, resource), actions))
        return permissions

    # Processing (override these)

    def process(self):
        self._process_services()
        self._process_regions()
        self._process_resources()
        self._process_actions()

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

    # resources = defaultdict(set)
    @abc.abstractmethod
    def _get_resources(self, filename, file, resources, region, account, service):
        pass

    # actions = set()
    @abc.abstractmethod
    def _get_actions(self, filename, file, actions, region, account, resource, service):
        pass

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
        ...     'dynamodb': {'us-west-1': {'111': {'Table/a': set(), 'Table/b': set()}}},
        ...     'ses': defaultdict(dict, {'*': {'111': {'*': set()}, '222': {'*': set()}}})
        ...     }
        >>> runtime._process_regions()
        >>> mock.calls_for('Base._walk')
        Runtime, _get_regions, {'us-east-1', 'us-east-2'}, account='111', service='ses'
        Runtime, _get_regions, {'us-east-1', 'us-east-2'}, account='222', service='ses'
        >>> pprint(normalize_dict(runtime._permissions))
        {'dynamodb': {'us-west-1': {'111': {'Table/a': set(), 'Table/b': set()}}},
         'ses': {'us-east-1': {'111': {'*': set()}, '222': {'*': set()}}, 'us-east-2': {'111': {'*': set()}, '222': {'*': set()}}}}
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
                    self._walk(
                            self._get_resources,
                            # custom arguments to processor
                            resources,
                            region=region,
                            account=account,
                            service=service,
                            )
                    self._normalize_resources(resources, (service, region, account))

    def _process_actions(self):
        for service, regions in self._permissions.items():
            for region, accounts in regions.items():
                for account, resources in accounts.items():
                    for resource, actions in resources.items():
                        self._walk(
                                self._get_actions,
                                # custom arguments to processor
                                actions,
                                region=region,
                                account=account,
                                service=service,
                                resource=resource,
                                )
                        self._normalize_actions(actions, (service, region, account, resource))

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
        client = Base.CLIENTS_CACHE.get((service, region, account))
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
        """ Convert dict to match-all when there's at least one.

        >>> from pprint import pprint
        >>> from test.utils import normalize_dict
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account', environment={})

        >>> resources = {'a': {'x'}, 'b': {'y'}, 'c': {'z'}}
        >>> runtime._normalize_resources(resources, ['dynamodb', 'us-west-1'])
        >>> pprint(resources)
        {'a': {'x'}, 'b': {'y'}, 'c': {'z'}}

        >>> resources = {'a': {'x'}, '*/*': {'y'}, 'c': {'z'}}
        >>> runtime._normalize_resources(resources, ['dynamodb', 'us-west-1'])
        >>> pprint(normalize_dict(resources))
        {'*/*': {'x', 'y', 'z'}}

        >>> mock.mock(None, 'eprint')
        >>> resources = defaultdict(set)
        >>> runtime._normalize_resources(resources, ['dynamodb', 'us-west-1'])
        >>> mock.calls_for('eprint')
        "warn: unknown permissions for 'dynamodb:us-west-1'"
        >>> dict(resources)
        {'*': set()}
        """

        if not resources:
            resources['*'] # accessing to initialize defaultdict
            eprint("warn: unknown permissions for '{}'".format(':'.join(parents)))
        else:
            for match_all in Base.MATCH_ALL_RESOURCES:
                if match_all in resources:
                    merged = set()
                    merged.update(*resources.values())
                    resources.clear()
                    resources[match_all] = merged
                    break

    def _normalize_actions(self, actions, parents):
        """ Convert set to match-all when there's at least one.

        >>> from pprint import pprint
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account', environment={})

        >>> actions = {'a', 'b', 'c'}
        >>> runtime._normalize_actions(actions, ['dynamodb', 'us-west-1', 'Table/SomeTable'])
        >>> sorted(actions)
        ['a', 'b', 'c']

        >>> actions = {'a', '*', 'c'}
        >>> runtime._normalize_actions(actions, ['dynamodb', 'us-west-1', 'Table/SomeTable'])
        >>> actions
        {'*'}

        >>> mock.mock(None, 'eprint')
        >>> actions = set()
        >>> runtime._normalize_actions(actions, ['dynamodb', 'us-west-1', 'Table/SomeTable'])
        >>> mock.calls_for('eprint')
        "warn: unknown permissions for 'dynamodb:us-west-1:Table/SomeTable'"
        >>> actions
        {'*'}
        """
        if not actions:
            actions.add('*')
            eprint("warn: unknown permissions for '{}'".format(':'.join(parents)))
        elif '*' in actions:
            actions.clear()
            actions.add('*')

