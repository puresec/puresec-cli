from collections import defaultdict
from functools import partial
from importlib import import_module
import aws_parsecf
import boto3
import botocore
import json
import os
import re
import yaml
import weakref

from puresec_cli.actions.generate_roles.providers.base import Base
from puresec_cli.actions.generate_roles.providers.aws_api import AwsApi
from puresec_cli.actions.generate_roles.runtimes import aws as runtimes
from puresec_cli.utils import eprint, capitalize

class AwsProvider(Base, AwsApi):
    def __init__(self, path, config, resource_template=None, runtime=None, framework=None, function=None, args=None):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(AwsProvider, '_init_default_account')

        >>> AwsProvider("path/to/project", config={})
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        'error: must supply either --resource-template, --runtime, or --framework'

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{}') and None
        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json", runtime='nodejs') and None
        >>> mock.calls_for('eprint')
        'warn: ignoring --runtime when --resource-template or --framework supplied'
        """

        super().__init__(
            path, config,
            resource_template=resource_template,
            runtime=runtime,
            framework=framework,
            function=function,
            args=args
        )

        if not self.resource_template and not self.runtime:
            eprint("error: must supply either --resource-template, --runtime, or --framework")
            raise SystemExit(2)
        if self.resource_template and self.runtime:
            eprint("warn: ignoring --runtime when --resource-template or --framework supplied")

        self._init_session()
        self._init_default_region()
        self._init_default_account()
        self._init_cloudformation_template()

    @property
    def permissions(self):
        return dict((name, permissions) for name, permissions in self._function_permissions.items())

    def role_name(self, name):
        parts = ['puresec', name]
        if self.framework:
            role_prefix = self.framework.role_prefix(name)
            parts.insert(0, role_prefix)
        return '-'.join(parts)

    TEMPLATE_DUMPERS = {
        '.json': partial(json.dumps, indent=2),
        '.yml': partial(yaml.dump, default_flow_style=False),
        '.yaml': partial(yaml.dump, default_flow_style=False),
    }

    @property
    def roles(self):
        roles = {}
        for name, function_permissions in self.permissions.items():
            role = roles["PureSec{}Role".format(capitalize(name))] = {
                'Type': 'AWS::IAM::Role',
                'Properties': {
                    'Path': '/',
                    'RoleName': self.role_name(name),
                    'AssumeRolePolicyDocument': {
                        'Version': '2012-10-17',
                        'Statement': [
                            {
                                'Effect': 'Allow',
                                'Action': 'sts:AssumeRole',
                                'Principal': {'Service': 'lambda.amazonaws.com'},
                            }
                        ]
                    }
                }
            }

            if function_permissions:
                role['Properties']['Policies'] = [{
                    'PolicyName': 'PureSecGeneratedRoles',
                    'PolicyDocument': {
                        'Version': '2012-10-17',
                        'Statement': [
                            {'Effect': 'Allow', 'Action': list(actions), 'Resource': resource}
                            for resource, actions in function_permissions.items()
                        ]
                    }
                }]
        return roles

    def result(self):
        resources = {'Resources': self.roles()}
        print(AwsProvider.TEMPLATE_DUMPERS[self.cloudformation_filetype or '.yml'](resources))

    def _init_session(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(AwsProvider, '_init_default_account')

        >>> from puresec_cli.actions.generate_roles.frameworks.base import Base as FrameworkBase
        >>> class Framework(FrameworkBase):
        ...     def _init_executable(self): pass
        ...     def get_default_profile(self):
        ...         return "default_profile"

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{ "a": { "b": 1 } }') and None

        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json").session
        Session(region_name=None)

        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json", framework=Framework("", {}, executable=None)).session
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: failed to create aws session:\\n{}', ProfileNotFound('The config profile (default_profile) could not be found',)
        """

        if self.framework:
            profile = self.framework.get_default_profile()
        else:
            profile = None

        try:
            self.session = boto3.Session(profile_name=profile)
        except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
            eprint("error: failed to create aws session:\n{}", e)
            raise SystemExit(-1)

    def _init_default_region(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(AwsProvider, '_init_default_account')

        >>> from puresec_cli.actions.generate_roles.frameworks.base import Base as FrameworkBase
        >>> class Framework(FrameworkBase):
        ...     def __init__(self, has_default_region):
        ...         self.has_default_region = has_default_region
        ...     def get_default_region(self):
        ...         return "framework-region" if self.has_default_region else None

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{}') and None

        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json", framework=Framework(True)).default_region
        'framework-region'

        >>> def _init_session(self):
        ...     self.session = boto3.Session(region_name='session-region')
        >>> mock.mock(AwsProvider, '_init_session', _init_session)

        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json", framework=Framework(False)).default_region
        'session-region'
        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json").default_region
        'session-region'

        >>> def _init_session(self):
        ...     self.session = boto3.Session(region_name=None)
        >>> mock.mock(AwsProvider, '_init_session', _init_session)
        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json", framework=Framework(False)).default_region
        '*'
        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json").default_region
        '*'
        """

        self.default_region = None
        # from framework
        if self.framework:
            self.default_region = self.framework.get_default_region()
        # from default config (or ENV)
        if not self.default_region:
            self.default_region = self.session.region_name

        if not self.default_region:
            self.default_region = '*'

    def _init_default_account(self):
        try:
            self.default_account = self.session.client('sts').get_caller_identity()['Account']
        except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
            eprint("error: failed to get account from aws:\n{}", e)
            raise SystemExit(-1)

    TEMPLATE_LOADERS = {
            '.json': aws_parsecf.load_json,
            '.yaml': aws_parsecf.load_yaml,
            '.yml': aws_parsecf.load_yaml,
            }

    def _init_cloudformation_template(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(AwsProvider, '_init_default_account')

        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json")
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        'error: could not find CloudFormation template in: {}', 'path/to/cloudformation.json'

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write("not a JSON") and None
        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json")
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint') # ValueError for <=3.4, JSONDecodeError for >=3.5
        'error: invalid CloudFormation template:\\n{}', ...Error('Expecting value: line 1 column 1 (char 0)',)

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{ "a": { "b": 1 } }') and None
        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json").cloudformation_template
        {'a': {'b': 1}}
        """

        if not self.resource_template:
            self.cloudformation_template = None
            self.cloudformation_filetype = None
            return

        _, self.cloudformation_filetype = os.path.splitext(self.resource_template)

        try:
            resource_template = open(self.resource_template, 'r', errors='replace')
        except FileNotFoundError:
            eprint("error: could not find CloudFormation template in: {}", self.resource_template)
            raise SystemExit(2)

        with resource_template:
            try:
                self.cloudformation_template = AwsProvider.TEMPLATE_LOADERS[self.cloudformation_filetype](resource_template, default_region=self.default_region)
            except ValueError as e:
                eprint("error: invalid CloudFormation template:\n{}", e)
                raise SystemExit(-1)

    def process(self):
        """
        >>> from pprint import pprint
        >>> from tests.utils import normalize_dict
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(AwsProvider, '_init_default_account')
        >>> mock.mock(AwsProvider, '_process_configurations')
        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{}') and None
        >>> from puresec_cli.actions.generate_roles.frameworks.base import Base as FrameworkBase
        >>> class Framework(FrameworkBase):
        ...     def _init_executable(self): pass
        ...     def get_function_name(self, name):
        ...         return name[1:]

        >>> from puresec_cli.actions.generate_roles.runtimes.aws.base import Base as RuntimeBase
        >>> class RuntimeModule:
        ...     class Runtime(RuntimeBase):
        ...         def process(self):
        ...             pass
        >>> mock.mock(None, 'import_module', lambda name: RuntimeModule)

        >>> handler = AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json", framework=Framework("", {}, executable=None))
        >>> handler.default_region = "default_region"
        >>> handler.default_account = "default_account"
        >>> mock.mock(handler, '_get_function_root', lambda name: "functions/{}".format(name))

        >>> handler.cloudformation_template = {
        ...     'Resources': {
        ...         'ResourceId': {
        ...             'Type': 'NotLambda'
        ...         }
        ...     }
        ... }
        >>> handler.process()
        >>> handler._function_permissions
        {}

        >>> handler.cloudformation_template = {
        ...     'Resources': {
        ...         'ResourceId': {
        ...             'Type': 'AWS::Lambda::Function'
        ...         }
        ...     }
        ... }
        >>> handler.process()
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        'error: lambda name not specified at `{}`', 'ResourceId'

        >>> handler.cloudformation_template = {
        ...     'Resources': {
        ...         'ResourceId': {
        ...             'Type': 'AWS::Lambda::Function',
        ...             'Properties': {
        ...                 'FunctionName': "-functionName"
        ...             }
        ...         }
        ...     }
        ... }
        >>> handler.process()
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        'error: lambda runtime not specified for `{}`', 'functionName'

        >>> handler.cloudformation_template = {
        ...     'Resources': {
        ...         'ResourceId': {
        ...             'Type': 'AWS::Lambda::Function',
        ...             'Properties': {
        ...                 'FunctionName': "-functionName",
        ...                 'Runtime': "abc4.3"
        ...             }
        ...         }
        ...     }
        ... }
        >>> handler.process()
        >>> mock.calls_for('eprint')
        'warn: lambda runtime not yet supported: `{}` (for `{}`)', 'abc', 'functionName'
        >>> handler._function_permissions
        {}

        >>> handler.cloudformation_template = None
        >>> handler.runtime = 'nodejs'
        >>> handler.process()
        >>> mock.calls_for('import_module')
        'puresec_cli.actions.generate_roles.runtimes.aws.nodejs'
        >>> list(handler._function_permissions.keys())
        ['nnamed']

        >>> handler.cloudformation_template = {
        ...     'Resources': {
        ...         'ResourceId': {
        ...             'Type': 'AWS::Lambda::Function',
        ...             'Properties': {
        ...                 'FunctionName': "-functionName",
        ...                 'Runtime': "nodejs4.3"
        ...             }
        ...         }
        ...     }
        ... }
        >>> handler.process()
        >>> mock.calls_for('import_module')
        'puresec_cli.actions.generate_roles.runtimes.aws.nodejs'
        >>> list(handler._function_permissions.keys())
        ['functionName']

        >>> handler.function = 'functionOne'
        >>> handler.cloudformation_template = {
        ...     'Resources': {
        ...         'FunctionOneId': {
        ...             'Type': 'AWS::Lambda::Function',
        ...             'Properties': {
        ...                 'FunctionName': "-functionOne",
        ...                 'Runtime': "nodejs4.3"
        ...             }
        ...         },
        ...         'FunctionTwoId': {
        ...             'Type': 'AWS::Lambda::Function',
        ...             'Properties': {
        ...                 'FunctionName': "-functionTwo",
        ...                 'Runtime': "nodejs4.3"
        ...             }
        ...         }
        ...     }
        ... }
        >>> handler.process()
        >>> list(handler._function_permissions.keys())
        ['functionOne']
        """
        self._function_real_names = {}
        self._function_permissions = {}

        if self.cloudformation_template:
            resources = self.cloudformation_template.get('Resources', {})
        else:
            resources = {
                'UnnamedFunction': {
                    'Type': 'AWS::Lambda::Function',
                    'Properties': {
                        'FunctionName': 'Unnamed',
                        'Runtime': self.runtime,
                    }
                }
            }

        for resource_id, resource_config in resources.items():
            if resource_config.get('Type') == 'AWS::Lambda::Function':
                # Getting name
                name = resource_config.get('Properties', {}).get('FunctionName')
                if not name:
                    eprint("error: lambda name not specified at `{}`", resource_id)
                    raise SystemExit(2)
                if self.framework:
                    name = self.framework.get_function_name(name)

                if self.function and self.function != name:
                    continue

                root = os.path.join(self.path, self._get_function_root(name))
                # Getting runtime
                runtime = resource_config.get('Properties', {}).get('Runtime')
                if not runtime:
                    eprint("error: lambda runtime not specified for `{}`", name)
                    raise SystemExit(2)

                runtime = re.sub(r"[\d\.]+$", '', runtime) # ignoring runtime version (e.g nodejs4.3)

                if runtime not in runtimes.__all__:
                    eprint("warn: lambda runtime not yet supported: `{}` (for `{}`)", runtime, name)
                    continue

                runtime = import_module("puresec_cli.actions.generate_roles.runtimes.aws.{}".format(runtime)).Runtime(
                    root,
                    resource_properties=resource_config['Properties'],
                    provider=weakref.proxy(self),
                )

                runtime.process()
                self._function_permissions[name] = runtime.permissions
                self._process_configurations(name, resource_id, resource_config)

    def _process_configurations(self, name, resource_id, resource_config):
        for processor in AwsProvider.CONFIGURATION_PROCESSORS:
            processor(self)(name, resource_id, resource_config)

Provider = AwsProvider

