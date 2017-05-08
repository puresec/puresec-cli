from collections import defaultdict
from copy import deepcopy
from importlib import import_module
from .base import Base
from ..runtimes import aws as runtimes
from ..utils import deepmerge, eprint
import boto3
import botocore
import json
import re

class Handler(Base):
    def __init__(self, path, config, resource_template=None, framework=None):
        super().__init__(path, config, resource_template, framework)

        try:
            resource_template = open(self.resource_template, 'r')
        except FileNotFoundError:
            eprint("error: could not find cloud formation template in: {}".format(self.resource_template))
            raise SystemExit(2)

        with resource_template:
            try:
                self.cloudformation_template = json.load(resource_template)
            except ValueError as e:
                eprint("error: invalid cloud formation template:\n{}".format(e))
                raise SystemExit(-1)

        self.init_session()
        self.init_default_region()
        self.init_default_account()

    def init_session(self):
        if self.framework:
            profile = self.framework.get_default_profile()
        else:
            profile = None
        try:
            self.session = boto3.Session(profile_name=profile)
        except botocore.exceptions.BotoCoreError as e:
            eprint("error: failed to create aws session:\n{}".format(e))
            raise SystemExit(-1)

    def init_default_region(self):
        if self.framework:
            # from framework
            self.default_region = self.framework.get_default_region()

        if not self.default_region:
            # from default config (or ENV)
            self.default_region = self.session.region_name

        if not self.default_region:
            self.default_region = '*'

    def init_default_account(self):
        try:
            self.default_account = self.session.client('sts').get_caller_identity()['Account']
        except botocore.exceptions.BotoCoreError as e:
            eprint("error: failed to get account from aws:\n{}".format(e))
            raise SystemExit(-1)

    def process(self):
        self._function_permissions = {}
        for resource_id, resource_config in self.cloudformation_template.get('Resources', {}).items():
            if resource_config['Type'] == 'AWS::Lambda::Function':
                # Getting name
                name = resource_config.get('Properties', {}).get('FunctionName')
                if not name:
                    eprint("error: lambda name not specified for '{}'".format(resource_id))
                    raise SystemExit(2)
                if self.framework:
                    name = self.framework.fix_name(name)
                # Getting runtime
                runtime = resource_config.get('Properties', {}).get('Runtime')
                if not runtime:
                    eprint("error: lambda runtime not specified for '{}'".format(name))
                    raise SystemExit(2)
                runtime = re.sub(r"[\d\.]+$", '', runtime) # ignoring runtime version (e.g nodejs4.3)
                if runtime not in runtimes.__all__:
                    eprint("warn: lambda runtime not supported for '{}' (for '{}'), sorry :(".format(runtime, name))
                    continue
                runtime = import_module(".runtimes.aws.{}".format(runtime), 'lib')
                # Getting environment
                environment = resource_config.get('Properties', {}).get('Environment', {}).get('Variables', {})

                # { service: { region: { account: { resource } } } }
                self._function_permissions[name] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

                self._process_function_services(name, runtime, environment)
                self._process_function_regions(name, runtime, environment)
                self._process_function_resources(name, runtime, environment)

    def _process_function_services(self, name, runtime, environment):
        super()._process_function(
                name,
                runtime.get_services,
                # custom arguments to processor
                self._function_permissions[name],
                default_region=self.default_region,
                default_account=self.default_account,
                environment=environment
                )

        self._normalize_permissions(self._function_permissions[name])

    def _process_function_regions(self, name, runtime, environment):
        # expanding '*' regions to all regions seen within the code
        for service, regions in self._function_permissions[name].items():
            if '*' in regions:
                for account, resources in regions['*'].items():
                    possible_regions = set()
                    super()._process_function(
                            name,
                            runtime.get_regions,
                            # custom arguments to processor
                            possible_regions,
                            service=service,
                            environment=environment
                            )
                    # moving the account from '*' to possible regions
                    if possible_regions:
                        for region in possible_regions:
                            regions[region][account] = deepcopy(resources)
                        del regions['*'][account]

                if not regions['*']:
                    # all moved
                    del regions['*']

    def _process_function_resources(self, name, runtime, environment):
        for service, regions in self._function_permissions[name].items():
            for region, accounts in regions.items():
                for account, resources in accounts.items():
                    if region == '*' or account == '*':
                        resources.add('*')
                        continue
                    super()._process_function(
                            name,
                            runtime.get_resources,
                            # custom arguments to processor
                            resources,
                            client=self._get_client(service, region, account),
                            service=service,
                            environment=environment
                            )
                    self._normalize_resources(resources, (service, region, account))

    def _normalize_permissions(self, tree):
        """ Merge trees when one of the keys have '*' permission """

        if '*' in tree:
            merged = reduce(deepmerge, tree.values())
            tree.clear()
            tree['*'] = merged

        for k, v in tree.items():
            if type(v) is dict:
                self._normalize_permissions(v)

    MATCH_ALL_RESOURCES = ('*', '*/*', '*:*')
    def _normalize_resources(self, resources, parents):
        if not resources:
            resources.add('*')
            eprint("warn: unknown permissions for '{}'", repr(parents))
        else:
            for match_all in Handler.MATCH_ALL_RESOURCES:
                if match_all in resources:
                    resources.clear()
                    resources.add(match_all)
                    break

    # { service: { region: { account: client } } }
    CLIENTS_CACHE = defaultdict(lambda: defaultdict(dict))
    def _get_client(self, service, region, account):
        client = Handler.CLIENTS_CACHE[service][region].get(account)
        if client:
            return client # from cache

        if account == self.default_account:
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

        Handler.CLIENTS_CACHE[service][region][account] = client
        return client

