from collections import defaultdict, namedtuple
from copy import deepcopy
from functools import reduce
from puresec_cli.actions.generate_roles.runtimes.base import Base as RuntimeBase
from puresec_cli.actions.generate_roles.runtimes.aws.base_api import BaseApi
from puresec_cli.utils import deepmerge, eprint
import abc
import boto3
import botocore
import fnmatch
import re

class Base(RuntimeBase, BaseApi):
    __metaclass__ = abc.ABCMeta

    def __init__(self, root, resource_properties, provider):
        super().__init__(root, provider)
        self.resource_properties = resource_properties

        self.environment_variables = self.resource_properties.get('Environment', {}).get('Variables', {})

        # { service: { region: { account: { resource: {action} } } } }
        self._permissions = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(set))))

    @property
    def permissions(self):
        """
        >>> from pprint import pprint

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', resource_properties={}, provider=object())
        >>> runtime._permissions = {
        ...     'dynamodb': {'us-west-1': {'111': {'table/a': {'GetRecords'}, 'table/b': {'UpdateItem'}}}},
        ...     'ses': {'*': {'111': {'*': {'*'}}, '222': {'*': {'*'}}}},
        ... }

        >>> pprint(runtime.permissions)
        {'arn:aws:dynamodb:us-west-1:111:table/a': {'GetRecords'},
         'arn:aws:dynamodb:us-west-1:111:table/b': {'UpdateItem'},
         'arn:aws:ses:*:111:*': {'*'},
         'arn:aws:ses:*:222:*': {'*'}}
        """

        permissions = {}
        for service, regions in self._permissions.items():
            for region, accounts in regions.items():
                for account, resources in accounts.items():
                    for resource, actions in resources.items():
                        permissions["arn:aws:{}:{}:{}:{}".format(service, region, account, resource)] = actions
        return permissions

    # Processing (override these)

    def process(self):
        self._process_services()
        self._process_regions()
        self._process_resources()
        self._process_actions()

        self._cleanup()

    @abc.abstractmethod
    def _get_services(self, filename, contents):
        pass

    try:
        REGION_PATTERNS = dict(
                (region, re.compile(r"\b{}\b".format(re.escape(region))))
                for region in boto3.Session().get_available_regions('ec2')
                )
    except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        eprint("error: failed to create aws session:\n{}", e)
        raise SystemExit(-1)
    # regions = set()
    def _get_regions(self, filename, contents, regions, service, account):
        """
        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', resource_properties={'Environment': {'Variables': {'var1': "gigi eu-west-1 laus-east-2", 'var2': "eu-central-1 ca-central-1" }}}, provider=object())

        >>> regions = set()
        >>> runtime._get_regions('filename', "lalala us-east-1 lululu us-west-1 us-east-2la us-west-5 nonono", regions, 'dynamodb', '*')
        >>> sorted(regions)
        ['ca-central-1', 'eu-central-1', 'eu-west-1', 'us-east-1', 'us-west-1']
        """

        # From file
        regions.update(
            region for region, pattern in Base.REGION_PATTERNS.items()
            if pattern.search(contents)
        )
        # From environment
        if not hasattr(self, '_environment_regions'):
            self._environment_regions = set(
                region for region, pattern in Base.REGION_PATTERNS.items()
                if any(pattern.search(value) for value in self.environment_variables.values() if isinstance(value, str))
            )
        regions.update(self._environment_regions)

    # resources = defaultdict(set)
    @abc.abstractmethod
    def _get_resources(self, filename, contents, resources, region, account, service):
        pass

    # actions = set()
    @abc.abstractmethod
    def _get_actions(self, filename, contents, actions, service):
        pass

    # Sub processors

    def _process_services(self):
        self._walk(self._get_services)
        self._normalize_permissions(self._permissions)

    def _process_regions(self):
        """ Expands '*' regions to all regions seen within the code.

        >>> from pprint import pprint
        >>> from tests.utils import normalize_dict
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', resource_properties={}, provider=object())

        >>> mock.mock(Base, '_walk', lambda self, processor, possible_regions, service, account: possible_regions.update({'us-east-1', 'us-east-2'}))
        >>> runtime._permissions = {
        ...     'dynamodb': {'us-west-1': {'111': {'table/a': set(), 'table/b': set()}}},
        ...     'ses': defaultdict(dict, {'*': {'111': {'*': set()}, '222': {'*': set()}}})
        ... }
        >>> runtime._process_regions()
        >>> mock.calls_for('Base._walk')
        Runtime, _get_regions, {'us-east-1', 'us-east-2'}, account='111', service='ses'
        Runtime, _get_regions, {'us-east-1', 'us-east-2'}, account='222', service='ses'
        >>> pprint(normalize_dict(runtime._permissions))
        {'dynamodb': {'us-west-1': {'111': {'table/a': set(), 'table/b': set()}}},
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
            actions = set()
            self._walk(
                self._get_actions,
                # custom arguments to processor
                actions,
                service=service,
            )

            for region, accounts in regions.items():
                for account, resources in accounts.items():
                    self._match_resources_actions(service, resources, actions)

                    self._normalize_actions(resources, (service, region, account))

    # get_all_resources_method: (region, account) => {resource: pattern}
    def _get_generic_resources(self, filename, contents, resources, region, account, resource_format, get_all_resources_method):
        """ Simply greps resources inside the given contents.

        >>> from collections import defaultdict
        >>> from functools import partial
        >>> from pprint import pprint
        >>> from tests.mock import Mock
        >>> from tests.utils import normalize_dict
        >>> mock = Mock(__name__)

        >>> class Provider:
        ...     pass
        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', resource_properties={'Environment': {'Variables': {'var1': "gigi table-1 latable-6", 'var2': "table-2 table-3"}}}, provider=Provider())
        >>> runtime.provider.cloudformation_template = None

        >>> mock.mock(runtime.provider, 'get_cached_api_result', {'TableNames': ["table-1", "table-2", "table-3", "table-4", "table-5", "table-6"]})

        >>> resources = defaultdict(set)
        >>> runtime._get_generic_resources('filename', "lalala table-4 lululu table-5 table-6la table-7 nonono", resources, region='us-east-1', account='some-account',
        ...                                resource_format="table/{}", get_all_resources_method=partial(runtime._get_generic_all_resources, 'dynamodb', template_type='AWS::DynamoDB::Table', api_method='list_tables', api_attribute='TableNames'))
        >>> pprint(normalize_dict(resources))
        {'table/table-1': set(), 'table/table-2': set(), 'table/table-3': set(), 'table/table-4': set(), 'table/table-5': set()}
        >>> mock.calls_for('Provider.get_cached_api_result')
        'dynamodb', account='some-account', api_kwargs={}, api_method='list_tables', region='us-east-1'
        """

        all_resources = get_all_resources_method(region=region, account=account)
        if not all_resources:
            resources[resource_format.format('*')]
            return

        # From file
        for resource, pattern in all_resources.items():
            if pattern.search(contents):
                resources[resource_format.format(resource)]

        # From environment
        for resource, pattern in all_resources.items():
            if any(pattern.search(value) for value in self.environment_variables.values() if isinstance(value, str)):
                resources[resource_format.format(resource)]

    def _match_resources_actions(self, service, resources, actions):
        """
        >>> from pprint import pprint
        >>> from tests.utils import normalize_dict

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', resource_properties={}, provider=object())

        >>> resources = defaultdict(set, {'table/sometable': set(), 'table/sometable/stream/somestream': set()})
        >>> actions = {'dynamodb:PutItem', 'dynamodb:GetRecords', 'dynamodb:DeleteItem', 'dynamodb:DescribeStream', 'dynamodb:ListTables'}
        >>> runtime._match_resources_actions('dynamodb', resources, actions)
        >>> pprint(normalize_dict(resources))
        {'*': {'dynamodb:ListTables'}, 'table/sometable': {'dynamodb:DeleteItem', 'dynamodb:PutItem'}, 'table/sometable/stream/somestream': {'dynamodb:DescribeStream', 'dynamodb:GetRecords'}}

        >>> resources = defaultdict(set, {'table/sometable': set()})
        >>> actions = {'dynamodb:GetRecords', 'dynamodb:DescribeStream'}
        >>> runtime._match_resources_actions('dynamodb', resources, actions)
        >>> pprint(normalize_dict(resources))
        {'table/*/stream/*': {'dynamodb:DescribeStream', 'dynamodb:GetRecords'}, 'table/sometable': set()}
        """

        matchers = Base.SERVICE_RESOURCE_ACTION_MATCHERS.get(service)

        if not matchers:
            if not resources:
                resources['*']
            # not specific matchers, just add all actions to all resources
            for resource, resource_actions in resources.items():
                resource_actions.update(actions)
            return

        unused_actions = set(actions)
        # matching with resources
        for resource, resource_actions in resources.items():
            for pattern, default, matching_actions in matchers:
                if pattern.match(resource):
                    matching = matching_actions.intersection(actions)
                    unused_actions.difference_update(matching)
                    resource_actions.update(matching)
                    break
        # adding unused actions to 'default' resources
        for action in unused_actions:
            for pattern, default, matching_actions in matchers:
                if action in matching_actions:
                    resources[default].add(action)

    def _cleanup(self):
        """ Merges region-less services and resource-less actions.

        >>> from pprint import pprint
        >>> from tests.utils import normalize_dict

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', resource_properties={}, provider=object())

        >>> runtime._permissions = {
        ...     'dynamodb': {'us-west-1': {'111': {'table/a': {'dynamodb:GetItem'}}}},
        ...     's3': defaultdict(dict, {'us-east-1': {'some-account': {'somebucket': {'s3:CreateBucket'}}}, 'us-west-1': {'another-account': {'anotherbucket': {'s3:ListObjects'}}}})
        ...     }
        >>> runtime._cleanup()
        >>> pprint(normalize_dict(runtime._permissions))
        {'dynamodb': {'us-west-1': {'111': {'table/a': {'dynamodb:GetItem'}}}},
         's3': {'': {'another-account': {'anotherbucket': {'s3:ListObjects'}}, 'some-account': {'*': {'s3:CreateBucket'}}}}}
        """
        # Region-less services
        for service in Base.REGIONLESS_SERVICES:
            if service not in self._permissions:
                continue
            merged = reduce(deepmerge, self._permissions[service].values())
            self._permissions[service].clear()
            self._permissions[service][''] = merged

        for service, resourceless_actions in Base.SERVICE_RESOURCELESS_ACTIONS.items():
            if service not in self._permissions:
                continue
            for region, accounts in self._permissions[service].items():
                for account, resources in accounts.items():
                    found_actions = set()
                    for resource, actions in tuple(resources.items()):
                        for action in resourceless_actions:
                            if action in actions:
                                found_actions.add(action)
                                actions.remove(action)
                        if not actions:
                            del resources[resource]
                    if found_actions:
                        resources['*'] = found_actions

    # Helpers

    def _normalize_permissions(self, tree):
        """ Merge trees when one of the keys have '*' permission.

        >>> from pprint import pprint
        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', resource_properties={}, provider=object())

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

    def _normalize_resources(self, resources, parents):
        """ Convert dict to match-all when there's at least one.

        >>> from pprint import pprint
        >>> from tests.utils import normalize_dict
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', resource_properties={}, provider=object())

        >>> resources = {'a': {'x'}, 'b': {'y'}, 'c': {'z'}}
        >>> runtime._normalize_resources(resources, ['dynamodb', 'us-west-1'])
        >>> pprint(resources)
        {'a': {'x'}, 'b': {'y'}, 'c': {'z'}}

        >>> resources = {'a': {'x'}, '*': {'y'}, 'c': {'z'}}
        >>> runtime._normalize_resources(resources, ['dynamodb', 'us-west-1'])
        >>> pprint(normalize_dict(resources))
        {'*': {'x', 'y', 'z'}}

        >>> resources = {'activity/b': {'z'}, 'execution/*': {'*'}, 'stateMachine/a': {'x'}, 'stateMachine/*': {'y'}}
        >>> runtime._normalize_resources(resources, ['dynamodb', 'us-west-1'])
        >>> pprint(normalize_dict(resources))
        {'activity/b': {'z'}, 'execution/*': {'*'}, 'stateMachine/*': {'x', 'y'}}

        >>> mock.mock(None, 'eprint')

        >>> resources = defaultdict(set)
        >>> runtime._normalize_resources(resources, ['dynamodb', 'us-west-1'])
        >>> mock.calls_for('eprint')
        "warn: unknown resources for '{}', couldn't find anything relevant in your AWS account or CloudFormation, falling back to '*'", 'dynamodb:us-west-1'
        >>> dict(resources)
        {'*': set()}
        """

        if not resources:
            resources['*'] # accessing to initialize defaultdict
            eprint("warn: unknown resources for '{}', couldn't find anything relevant in your AWS account or CloudFormation, falling back to '*'", ':'.join(parents))
        else:
            # mapping all resources wildcard matching to others
            wildcard_matches = {}
            for resource in resources.keys():
                if '*' in resource or '?' in resource:
                    matches = fnmatch.filter(resources.keys(), resource)
                    if len(matches) > 1: # not just self
                        wildcard_matches[resource] = matches

            for wildcard, matches in wildcard_matches.items():
                if wildcard not in resources:
                    continue # processed by another resource
                merged = set()
                for resource in matches:
                    if resource not in resources:
                        continue # processed by another resource
                    merged.update(resources[resource])
                    del resources[resource]
                resources[wildcard] = merged

    def _normalize_actions(self, resources, parents):
        """ Convert set to match-all when there's at least one.

        >>> from pprint import pprint
        >>> from tests.utils import normalize_dict
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Runtime(Base):
        ...     pass
        >>> runtime = Runtime('path/to/function', resource_properties={}, provider=object())

        >>> resources = {'table/sometable': {'a', 'b', 'c'}}
        >>> runtime._normalize_actions(resources, ['dynamodb', 'us-west-1'])
        >>> pprint(normalize_dict(resources))
        {'table/sometable': {'a', 'b', 'c'}}

        >>> resources = {'table/sometable': {'a', '*', 'c'}}
        >>> runtime._normalize_actions(resources, ['dynamodb', 'us-west-1'])
        >>> pprint(normalize_dict(resources))
        {'table/sometable': {'*'}}

        >>> resources = {'table/sometable': set(), 'table/sometable/stream/somestream': {'dynamodb:DescribeStream'}}
        >>> runtime._normalize_actions(resources, ['dynamodb', 'us-west-1'])
        >>> pprint(normalize_dict(resources))
        {'table/sometable/stream/somestream': {'dynamodb:DescribeStream'}}

        >>> resources = {'table/sometable/stream/somestream': set(), 'table/sometable': {'dynamodb:GetItem'}}
        >>> runtime._normalize_actions(resources, ['dynamodb', 'us-west-1'])
        >>> pprint(normalize_dict(resources))
        {'table/sometable': {'dynamodb:GetItem'}}

        >>> mock.mock(None, 'eprint')
        >>> resources = {'table/sometable': set()}
        >>> runtime._normalize_actions(resources, ['dynamodb', 'us-west-1'])
        >>> mock.calls_for('eprint')
        "warn: unknown actions for '{}:{}', couldn't find any relevant SDK methods in your code, falling back to '*'", 'dynamodb:us-west-1', 'table/sometable'
        >>> pprint(normalize_dict(resources))
        {'table/sometable': {'*'}}

        >>> resources = {'table/sometable': set(), 'table/sometable/stream/somestream': set()}
        >>> runtime._normalize_actions(resources, ['dynamodb', 'us-west-1'])
        >>> pprint(normalize_dict(resources))
        {'table/sometable': {'*'}, 'table/sometable/stream/somestream': {'*'}}
        """
        for resource, actions in tuple(resources.items()):
            if not actions:
                # if there are no other resources with common name that *do* have actions
                if any(
                        (other_resource.startswith(resource.rstrip('*')) or resource.startswith(other_resource.rstrip('*'))) and other_actions.difference({'*'})
                        for other_resource, other_actions in resources.items()):
                    # then it's fine
                    del resources[resource]
                else:
                    actions.add('*')
                    eprint("warn: unknown actions for '{}:{}', couldn't find any relevant SDK methods in your code, falling back to '*'", ':'.join(parents), resource)
            elif '*' in actions:
                actions.clear()
                actions.add('*')

