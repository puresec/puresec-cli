from base import Base
from collections import defaultdict
from copy import deepcopy
from importlib import import_module
from ..utils import deepmerge, eprint
import boto3
import json
import re

class Handler(Base):
    def __init__(self, code_path, config, resource_template=None, framework=None):
        super().__init__(code_path, config, resource_template, framework)

        with open(self.resource_template, 'rb') as resource_template:
            self.cloudformation_template = json.load(resource_template)

        self.init_default_profile()
        self.init_default_region()
        self.init_default_account()

    def init_default_profile(self):
        if self.framework:
            self.default_profile = self.framework.get_default_profile()
        else:
            self.default_profile = None

    def init_default_region(self):
        if self.framework:
            # from framework
            self.default_region = self.framework.get_default_region()

        if not self.default_region:
            # from default config (or ENV)
            self.default_region = boto3.Session(profile_name=self.default_profile).region_name

        if not self.default_region:
            self.default_region = '*'

    def init_default_account(self):
        self.default_account = boto3.client('sts', profile=self.default_profile).get_caller_identity()['Account']

    def process(self):
        self._function_permissions = {}
        for name, resource_config in self.cloudformation_template['Resources'].items():
            if resource_config['Type'] == 'AWS::Lambda::Function':
                # ignoring runtime version (e.g nodejs4.3)
                runtime = re.sub(r"[\d\.]+$", '', resource_config['Properties']['Runtime'])
                runtime = import_module(runtime, '..runtimes.aws')

                environment = resource_config['Properties']['Environment']['Variables']

                # { service: { region: { account: { resource } } } }
                self._function_permissions[name] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

                self._process_function_services(name, runtime, environment)
                self._process_function_regions(name, runtime, environment)
                self._process_function_resources(name, runtime, environment)

    def _process_function_services(self, name, runtime, environment):
        super()._process_function(
                name,
                runtime.get_permissions,
                # custom arguments to processor
                self._function_permissions[name],
                default_region=self.default_region,
                default_account=self.default_account,
                envrionment=environment
                )

        self._normalize_permissions(self._function_permissions[name])

    def _process_function_regiions(self, name, runtime, environment):
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
                            client=self._get_client(service, account),
                            service=service,
                            environment=envrionment
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
                            client=self._get_client(service, account),
                            service=service,
                            environment=envrionment
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
            eprint("WARNING: Unknown permissions for: {}", repr(parents))
        else:
            for match_all in Handler.MATCH_ALL_RESOURCES:
                if match_all in resources:
                    resources.clear()
                    resources.match_all()
                    break

    # { service: { region: { account: client } } }
    CLIENTS_CACHE = defaultdict(lambda: defaultdict(dict))
    def _get_client(self, service, region, account):
        client = Handler.CLIENTS_CACHE[service][region].get(account)
        if client:
            return client # from cache

        if account == self.default_account
            client = boto3.client(
                    service,
                    profile_name=self.default_profile,
                    region=region
                    )
        else:
            account_config = self.config.setdefault('aws', {}).setdefault('accounts', {}).setdefault(account, {})
            if not 'access_key_id' in account_config:
                account_config['access_key_id'] = input("Enter AWS access key id for {}: ".format(account))
                account_config['secret_access_key'] = input("Enter AWS secret access key for {}: ".format(account))
            client = boto3.client(
                    service,
                    profile_name=self.default_profile,
                    region=region,
                    access_key_id=account_config['access_key_id'],
                    secret_access_key=account_config['secret_access_key']
                    )

        Handler.CLIENTS_CACHE[service][region][account] = client
        return client

