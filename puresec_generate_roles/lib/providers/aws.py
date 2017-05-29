from importlib import import_module
from lib.providers.base import Base
from lib.runtimes import aws as runtimes
from lib.utils import eprint
import aws_parsecf
import boto3
import botocore
import os
import re

class AwsProvider(Base):
    def __init__(self, path, config, resource_template=None, framework=None):
        """
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(AwsProvider, '_init_default_account')

        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json")
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        'error: could not find CloudFormation template in: path/to/cloudformation.json'

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write("not a JSON") and None
        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json")
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: invalid CloudFormation template:\\nExpecting value: line 1 column 1 (char 0)'

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{ "a": { "b": 1 } }') and None
        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json").cloudformation_template
        {'a': {'b': 1}}
        """

        super().__init__(path, config, resource_template, framework)

        self._init_session()
        self._init_default_region()
        self._init_default_account()

        try:
            resource_template = open(self.resource_template, 'r', errors='replace')
        except FileNotFoundError:
            eprint("error: could not find CloudFormation template in: {}".format(self.resource_template))
            raise SystemExit(2)

        with resource_template:
            try:
                self.cloudformation_template = aws_parsecf.load_json(resource_template, default_region=self.default_region)
            except ValueError as e:
                eprint("error: invalid CloudFormation template:\n{}".format(e))
                raise SystemExit(-1)

    @property
    def format(self):
        return 'json'

    @property
    def output(self):
        resources = {}
        for name, runtime in self._function_runtimes.items():
            real_name = self._function_real_names[name]

            role = resources["{}Role".format(name)] = {
                    'Type': 'AWS:IAM:Role',
                    'Properties': {
                        'Path': '/',
                        'RoleName': real_name,
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

            policies = role['Properties']['Policies'] = [{
                'PolicyName': "CreateAndWriteToLogStream",
                'PolicyDocument': {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Action': 'logs:CreateLogStream',
                            'Resource': "arn:aws:logs:{}:{}:log-group:/aws/lambda/{}:*".format(self.default_region, self.default_account, real_name),
                            },
                        {
                            'Effect': 'Allow',
                            'Action': 'logs:PutLogEvents',
                            'Resource': "arn:aws:logs:{}:{}:log-group:/aws/lambda/{}:*:*".format(self.default_region, self.default_account, real_name),
                            },
                        ]
                    }
                }]
            permissions = runtime.permissions
            if permissions:
                policies.append({
                    'PolicyName': 'PureSecGeneratedRoles',
                    'PolicyDocument': {
                        'Version': '2012-10-17',
                        'Statement': [
                            {'Effect': 'Allow', 'Action': list(actions), 'Resource': resource}
                            for resource, actions in permissions
                            ]
                        }
                    })

        if resources:
            return {'Resources': resources}

    def _init_session(self):
        """
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(AwsProvider, '_init_default_account')

        >>> from lib.frameworks.base import Base as FrameworkBase
        >>> class Framework(FrameworkBase):
        ...     def get_default_profile(self):
        ...         return "default_profile"

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{ "a": { "b": 1 } }') and None

        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json").session
        Session(region_name=None)

        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json", framework=Framework("", 'ls', {})).session
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: failed to create aws session:\\nThe config profile (default_profile) could not be found'
        """
        if self.framework:
            profile = self.framework.get_default_profile()
        else:
            profile = None

        try:
            self.session = boto3.Session(profile_name=profile)
        except botocore.exceptions.BotoCoreError as e:
            eprint("error: failed to create aws session:\n{}".format(e))
            raise SystemExit(-1)

    def _init_default_region(self):
        """
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(AwsProvider, '_init_default_account')

        >>> from lib.frameworks.base import Base as FrameworkBase
        >>> class Framework(FrameworkBase):
        ...     def __init__(self, has_default_region):
        ...         self.has_default_region = has_default_region
        ...     def get_default_region(self):
        ...         return "framework-region" if self.has_default_region else None

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{}') and None

        >>> AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json", framework=Framework(True)).default_region
        'framework-region'

        >>> import boto3
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
        except botocore.exceptions.BotoCoreError as e:
            eprint("error: failed to get account from aws:\n{}".format(e))
            raise SystemExit(-1)

    def process(self):
        """
        >>> from pprint import pprint
        >>> from test.utils import normalize_dict
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(AwsProvider, '_init_default_account')
        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{}') and None
        >>> from lib.frameworks.base import Base as FrameworkBase
        >>> class Framework(FrameworkBase):
        ...     def get_function_name(self, name):
        ...         return name[1:]

        >>> from lib.runtimes.aws.base import Base as RuntimeBase
        >>> class RuntimeModule:
        ...     class Runtime(RuntimeBase):
        ...         def process(self):
        ...             self.processed = True
        >>> mock.mock(None, 'import_module', lambda name: RuntimeModule)

        >>> handler = AwsProvider("path/to/project", config={}, resource_template="path/to/cloudformation.json", framework=Framework("", 'ls', {}))
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
        >>> handler._function_runtimes
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
        'error: lambda name not specified at `ResourceId`'

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
        'error: lambda runtime not specified for `functionName`'

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
        'warn: lambda runtime not supported: `abc` (for `functionName`), sorry :('
        >>> handler._function_runtimes
        {}

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
        'lib.runtimes.aws.nodejs'
        >>> list(handler._function_runtimes.keys())
        ['functionName']
        >>> handler._function_runtimes['functionName'].root
        'path/to/project/functions/functionName'
        >>> handler._function_runtimes['functionName'].default_region
        'default_region'
        >>> handler._function_runtimes['functionName'].default_account
        'default_account'
        >>> handler._function_runtimes['functionName'].environment
        {}
        >>> handler._function_runtimes['functionName'].processed
        True

        >>> handler.cloudformation_template = {
        ...     'Resources': {
        ...         'ResourceId': {
        ...             'Type': 'AWS::Lambda::Function',
        ...             'Properties': {
        ...                 'FunctionName': "-functionName",
        ...                 'Runtime': "nodejs4.3",
        ...                 'Environment': {
        ...                     'Variables': { 'a': 1, 'b': 2 }
        ...                 }
        ...             }
        ...         }
        ...     }
        ... }
        >>> handler.process()
        >>> mock.calls_for('import_module')
        'lib.runtimes.aws.nodejs'
        >>> list(handler._function_runtimes.keys())
        ['functionName']
        >>> handler._function_runtimes['functionName'].root
        'path/to/project/functions/functionName'
        >>> handler._function_runtimes['functionName'].default_region
        'default_region'
        >>> handler._function_runtimes['functionName'].default_account
        'default_account'
        >>> pprint(handler._function_runtimes['functionName'].environment)
        {'a': 1, 'b': 2}
        >>> handler._function_runtimes['functionName'].processed
        True
        """
        self._function_real_names = {}
        self._function_runtimes = {}
        for resource_id, resource_config in self.cloudformation_template.get('Resources', {}).items():
            if resource_config['Type'] == 'AWS::Lambda::Function':
                # Getting name
                real_name = resource_config.get('Properties', {}).get('FunctionName')
                if not real_name:
                    eprint("error: lambda name not specified at `{}`".format(resource_id))
                    raise SystemExit(2)
                if self.framework:
                    name = self.framework.get_function_name(real_name)
                else:
                    name = real_name
                self._function_real_names[name] = real_name

                root = os.path.join(self.path, self._get_function_root(name))
                # Getting runtime
                runtime = resource_config.get('Properties', {}).get('Runtime')
                if not runtime:
                    eprint("error: lambda runtime not specified for `{}`".format(name))
                    raise SystemExit(2)
                runtime = re.sub(r"[\d\.]+$", '', runtime) # ignoring runtime version (e.g nodejs4.3)
                if runtime not in runtimes.__all__:
                    eprint("warn: lambda runtime not supported: `{}` (for `{}`), sorry :(".format(runtime, name))
                    continue
                # Getting environment
                environment = resource_config.get('Properties', {}).get('Environment', {}).get('Variables', {})

                self._function_runtimes[name] = runtime = import_module("lib.runtimes.aws.{}".format(runtime)).Runtime(
                        root,
                        config=self.config,
                        session=self.session,
                        default_region=self.default_region,
                        default_account=self.default_account,
                        environment=environment)

                runtime.process()

Provider = AwsProvider

