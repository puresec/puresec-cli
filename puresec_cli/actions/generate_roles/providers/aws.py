from functools import partial
from importlib import import_module
import json
import os
import re
import yaml
import weakref

from puresec_cli.actions.generate_roles.providers.base import Base
from puresec_cli.actions.generate_roles.providers.aws_api import AwsApi
from puresec_cli.actions.generate_roles.runtimes import aws as runtimes
from puresec_cli.providers.aws import Aws
from puresec_cli.utils import eprint, camelcase

class AwsProvider(AwsApi, Aws, Base):
    def __init__(self, path, config, resource_template=None, runtime=None, handler=None, function_name=None, framework=None, function=None, args=None):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

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

        Base.__init__(
            self,
            path, config,
            resource_template=resource_template,
            runtime=runtime,
            handler=handler,
            function_name=function_name,
            framework=framework,
            function=function,
            args=args
        )
        Aws.__init__(
            self,
            resource_template=self.resource_template,
            framework=self.framework,
        )

        if not self.resource_template and not self.runtime:
            eprint("error: must supply either --resource-template, --runtime, or --framework")
            raise SystemExit(2)
        if self.resource_template:
            if self.runtime:
                eprint("warn: ignoring --runtime when --resource-template or --framework supplied")
            if self.handler:
                eprint("warn: ignoring --handler when --resource-template or --framework supplied")
            if self.function_name:
                eprint("warn: ignoring --function-name when --resource-template or --framework supplied")

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
            role = roles["PureSec{}Role".format(camelcase(name))] = {
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
        resources = {'Resources': self.roles}
        result_format = (self.framework and self.framework.result_format) or self.cloudformation_filetype or '.yaml'
        print(AwsProvider.TEMPLATE_DUMPERS[result_format](resources))

    def process(self):
        """
        >>> from pprint import pprint
        >>> from tests.utils import normalize_dict
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(AwsProvider, '_process_configurations')
        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{}') and None
        >>> from puresec_cli.actions.generate_roles.frameworks.base import Base as FrameworkBase
        >>> class Framework(FrameworkBase):
        ...     def get_function_name(self, name):
        ...         return name[1:]

        >>> from puresec_cli.actions.generate_roles.runtimes.aws.base import Base as RuntimeBase
        >>> class RuntimeModule:
        ...     class Runtime(RuntimeBase):
        ...         def process(self):
        ...             pass
        >>> mock.mock(None, 'import_module', lambda name: RuntimeModule)

        >>> handler = AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json", framework=Framework("", {}))
        >>> mock.mock(AwsProvider, 'default_region', "default_region")
        >>> mock.mock(AwsProvider, 'default_account', "default_account")
        >>> mock.mock(handler, '_get_function_root', lambda name: "functions/{}".format(name))

        >>> mock.mock(AwsProvider, 'cloudformation_template', {
        ...     'Resources': {
        ...         'ResourceId': {
        ...             'Type': 'NotLambda'
        ...         }
        ...     }
        ... })
        >>> handler.process()
        >>> handler._function_permissions
        {}

        >>> mock.mock(AwsProvider, 'cloudformation_template', {
        ...     'Resources': {
        ...         'ResourceId': {
        ...             'Type': 'AWS::Lambda::Function'
        ...         }
        ...     }
        ... })
        >>> handler.process()
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        'error: lambda name not specified at `{}`', 'ResourceId'

        >>> mock.mock(AwsProvider, 'cloudformation_template', {
        ...     'Resources': {
        ...         'ResourceId': {
        ...             'Type': 'AWS::Lambda::Function',
        ...             'Properties': {
        ...                 'FunctionName': "-functionName"
        ...             }
        ...         }
        ...     }
        ... })
        >>> handler.process()
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        'error: lambda runtime not specified for `{}`', 'functionName'

        >>> mock.mock(AwsProvider, 'cloudformation_template', {
        ...     'Resources': {
        ...         'ResourceId': {
        ...             'Type': 'AWS::Lambda::Function',
        ...             'Properties': {
        ...                 'FunctionName': "-functionName",
        ...                 'Runtime': "abc4.3"
        ...             }
        ...         }
        ...     }
        ... })
        >>> handler.process()
        >>> mock.calls_for('eprint')
        'warn: lambda runtime not yet supported: `{}` (for `{}`)', 'abc', 'functionName'
        >>> handler._function_permissions
        {}

        >>> mock.mock(AwsProvider, 'cloudformation_template', None)
        >>> handler.runtime = 'nodejs'
        >>> handler.process()
        >>> mock.calls_for('import_module')
        'puresec_cli.actions.generate_roles.runtimes.aws.nodejs'
        >>> list(handler._function_permissions.keys())
        ['nnamed']

        >>> mock.mock(AwsProvider, 'cloudformation_template', {
        ...     'Resources': {
        ...         'ResourceId': {
        ...             'Type': 'AWS::Lambda::Function',
        ...             'Properties': {
        ...                 'FunctionName': "-functionName",
        ...                 'Runtime': "nodejs4.3"
        ...             }
        ...         }
        ...     }
        ... })
        >>> handler.process()
        >>> mock.calls_for('import_module')
        'puresec_cli.actions.generate_roles.runtimes.aws.nodejs'
        >>> list(handler._function_permissions.keys())
        ['functionName']

        >>> handler.function = 'functionOne'
        >>> mock.mock(AwsProvider, 'cloudformation_template', {
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
        ... })
        >>> handler.process()
        >>> list(handler._function_permissions.keys())
        ['functionOne']
        """
        self._function_real_names = {}
        self._function_permissions = {}

        if self.cloudformation_template:
            resources = self.cloudformation_template.get('Resources', {})
        else:
            function_name = self.function_name or 'Unnamed'
            resources = {
                '{}Function'.format(camelcase(function_name)): {
                    'Type': 'AWS::Lambda::Function',
                    'Properties': {
                        'FunctionName': function_name,
                        'Runtime': self.runtime,
                        'Handler': self.handler,
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

