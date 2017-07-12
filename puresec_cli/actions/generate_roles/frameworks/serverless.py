from ruamel.yaml import YAML
from tempfile import TemporaryDirectory
from zipfile import ZipFile, BadZipFile
import json
import os
import re
import subprocess

from puresec_cli.actions.generate_roles.frameworks.base import Base
from puresec_cli.utils import eprint, input_query, capitalize

yaml = YAML() # using non-breaking yaml now

class ServerlessFramework(Base):
    def __init__(self, path, config, executable=None, function=None, args=None):
        if not executable:
            executable = 'serverless' # from environment (PATH)

        super().__init__(
            path, config,
            executable=executable,
            function=function,
            args=args
        )

        self.query_suffix = " (only for `{}`)".format(self.function) if self.function else ""

        if os.path.exists(os.path.join(self.path, 'puresec-roles.yml')):
            if not (self.args.yes or self.args.overwrite) and (self.args.no_overwrite or not input_query("Roles file already exists, overwrite?{}", self.query_suffix)):
                raise SystemExit(1)

    def __exit__(self, type, value, traceback):
        super().__exit__(type, value, traceback)

        if hasattr(self, '_serverless_package'):
            self._serverless_package.cleanup()

    def role_prefix(self, name):
        return self._serverless_config['service']['service']

    def result(self, provider):
        permissions = provider.permissions
        if not permissions:
            return

        self._dump_roles(provider)

        # modifying serverless.yml

        config_path = os.path.join(self.path, "serverless.yml")
        with open(config_path, 'r') as f:
            config = yaml.load(f)

        new_resources = config.setdefault('resources', {}).setdefault('Resources', {})
        old_resources = self._serverless_config['service'].get('resources', {}).get('Resources', {})

        new_roles = self._add_roles(permissions, config, new_resources)
        old_roles = self._get_old_roles(config, old_resources, new_resources, new_roles)
        self._reference_roles(permissions, config)
        self._remove_old_roles(config, old_resources, new_resources, old_roles, new_roles)

        # deleting 'resources' from config if empty
        if not new_resources and 'resources' in config:
            del config['resources']

        with open(config_path, 'w') as f:
            yaml.dump(config, f)

    def _dump_roles(self, provider):
        """
        >>> from pprint import pprint
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(ServerlessFramework, '_init_executable')

        >>> class Provider:
        ...     pass
        >>> provider = Provider()
        >>> provider.roles = {'PureSecSomeRole': "some role", 'PureSecAnotherRole': "another role"}

        >>> class Args:
        ...     pass
        >>> args = Args()
        >>> args.yes = True

        >>> ServerlessFramework("path/to/project", {}, args=args)._dump_roles(provider)
        >>> with mock.open("path/to/project/puresec-roles.yml", 'r') as f:
        ...     pprint(dict(yaml.load(f)))
        {'PureSecAnotherRole': 'another role', 'PureSecSomeRole': 'some role'}
        >>> mock.clear_filesystem()

        >>> with mock.open("path/to/project/puresec-roles.yml", 'w') as f:
        ...     f.write("something to overwrite") and None
        >>> ServerlessFramework("path/to/project", {}, args=args)._dump_roles(provider)
        >>> with mock.open("path/to/project/puresec-roles.yml", 'r') as f:
        ...     pprint(dict(yaml.load(f)))
        {'PureSecAnotherRole': 'another role', 'PureSecSomeRole': 'some role'}
        >>> mock.clear_filesystem()

        >>> ServerlessFramework("path/to/project", {}, function="some", args=args)._dump_roles(provider)
        >>> with mock.open("path/to/project/puresec-roles.yml", 'r') as f:
        ...     pprint(dict(yaml.load(f)))
        {'PureSecSomeRole': 'some role'}
        >>> mock.clear_filesystem()

        >>> provider.roles = {'PureSecSomeRole': "changed role", 'PureSecAnotherRole': "another changed role"}
        >>> with mock.open("path/to/project/puresec-roles.yml", 'w') as f:
        ...     yaml.dump({'PureSecSomeRole': "some role", 'PureSecAnotherRole': "another role"}, f)
        >>> ServerlessFramework("path/to/project", {}, function="some", args=args)._dump_roles(provider)
        >>> with mock.open("path/to/project/puresec-roles.yml", 'r') as f:
        ...     pprint(dict(yaml.load(f)))
        {'PureSecAnotherRole': 'another role', 'PureSecSomeRole': 'changed role'}
        >>> mock.clear_filesystem()
        """

        path = os.path.join(self.path, 'puresec-roles.yml')
        if not self.function:
            # full dump
            with open(path, 'w') as f:
                yaml.dump(provider.roles, f)
        else:
            # partial dump (only specified function)
            try:
                with open(path, 'r') as f:
                    roles = yaml.load(f)
            except FileNotFoundError:
                roles = {}

            role_name = "PureSec{}Role".format(capitalize(self.function))
            roles[role_name] = provider.roles[role_name]
            with open(path, 'w') as f:
                yaml.dump(roles, f)

    def _add_roles(self, permissions, config, new_resources):
        """
        >>> from pprint import pprint
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(ServerlessFramework, '_init_executable')

        >>> permissions = {'some': "some permissions", 'another': "another permissions"}
        >>> config = {}
        >>> new_resources = {}

        >>> sorted(ServerlessFramework("path/to/project", {})._add_roles(permissions, config, new_resources))
        ['puresecAnotherRole', 'puresecSomeRole']
        >>> config
        {'custom': {'puresec_roles': '${file(puresec-roles.yml)}'}}
        >>> pprint(new_resources)
        {'puresecAnotherRole': '${self:custom.puresec_roles.PureSecAnotherRole}', 'puresecSomeRole': '${self:custom.puresec_roles.PureSecSomeRole}'}
        """

        new_roles = set()

        config.setdefault('custom', {})['puresec_roles'] = "${file(puresec-roles.yml)}"
        for name in permissions.keys():
            role = "puresec{}Role".format(capitalize(name))
            new_roles.add(role)
            new_resources[role] = "${{self:custom.puresec_roles.PureSec{}Role}}".format(capitalize(name))

        return new_roles

    def _get_old_roles(self, config, old_resources, new_resources, new_roles):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(ServerlessFramework, '_init_executable')

        >>> ServerlessFramework("path/to/project", {})._get_old_roles({}, {}, {}, set())
        []

        >>> config = {'provider': {'iamRoleStatements': "some roles"}}
        >>> ServerlessFramework("path/to/project", {})._get_old_roles(config, {}, {}, set())
        ['default service-level role (provider.iamRoleStatements)']

        >>> config = {'provider': {'iamRoleStatements': "some roles"}}
        >>> ServerlessFramework("path/to/project", {}, function="some")._get_old_roles(config, {}, {}, set())
        []

        >>> old_resources = {'someRole': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['lambda.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> new_resources = {'someRole': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['lambda.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> ServerlessFramework("path/to/project", {})._get_old_roles({}, old_resources, new_resources, set())
        ['someRole']

        >>> old_resources = {'someRole': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['lambda.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> new_resources = {'someRole': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['lambda.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> new_roles = {'someRole'}
        >>> ServerlessFramework("path/to/project", {})._get_old_roles({}, old_resources, new_resources, new_roles)
        []

        >>> old_resources = {'dynamodbTable': {'Type': 'AWS::DynamoDB::Table'}}
        >>> ServerlessFramework("path/to/project", {})._get_old_roles({}, old_resources, {}, set())
        []

        >>> old_resources = {'ec2Role': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['ec2.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> new_resources = {'ec2Role': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['ec2.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> ServerlessFramework("path/to/project", {})._get_old_roles({}, old_resources, new_resources, set())
        []

        >>> config = {'functions': {'some': {'role': "someRole"}}}
        >>> new_resources = {'someRole': "some role", 'anotherRole': "another role"}
        >>> ServerlessFramework("path/to/project", {}, function="some")._get_old_roles(config, {}, new_resources, set())
        ['someRole']

        >>> config = {'functions': {'some': {'role': "someRole"}}}
        >>> new_resources = {'someRole': "some role", 'anotherRole': "another role"}
        >>> new_roles = {'someRole'}
        >>> ServerlessFramework("path/to/project", {}, function="some")._get_old_roles(config, {}, new_resources, new_roles)
        []
        """

        old_roles = []

        # default role
        if not self.function and 'iamRoleStatements' in config.get('provider', ()):
            old_roles.append("default service-level role (provider.iamRoleStatements)")
        # specific roles
        if not self.function:
            # roles assumed for lambda
            for resource_id, resource_config in old_resources.items():
                if resource_config.get('Type') == 'AWS::IAM::Role':
                    # meh
                    if 'lambda.amazonaws.com' in str(resource_config.get('Properties', {}).get('AssumeRolePolicyDocument')):
                        if resource_id not in new_roles and resource_id in new_resources:
                            old_roles.append(resource_config.get('Properties', {}).get('RoleName', resource_id))
        else:
            # specified function's role
            role = config.get('functions', {}).get(self.function, {}).get('role')
            if role and role not in new_roles and role in new_resources:
                old_roles.append(role)

        return old_roles

    def _reference_roles(self, permissions, config):
        """
        >>> from pprint import pprint
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(ServerlessFramework, '_init_executable')

        >>> class Args:
        ...     pass
        >>> args = Args()
        >>> args.yes = True

        >>> permissions = {'some': "some permissions", 'another': "another permissions"}

        >>> config = {'functions': {'some': {}, 'another': {}}}
        >>> ServerlessFramework("path/to/project", {}, args=args)._reference_roles(permissions, config)
        >>> pprint(config)
        {'functions': {'another': {'role': 'puresecAnotherRole'}, 'some': {'role': 'puresecSomeRole'}}}

        >>> mock.mock(None, 'eprint')

        >>> config = {'functions': {'another': {}}}
        >>> ServerlessFramework("path/to/project", {}, args=args)._reference_roles(permissions, config)
        >>> pprint(config)
        {'functions': {'another': {'role': 'puresecAnotherRole'}}}
        >>> mock.calls_for('eprint')
        'warn: `{}` not found under the `functions` section in serverless.yml', 'some'

        >>> config = {}
        >>> ServerlessFramework("path/to/project", {}, args=args)._reference_roles(permissions, config)
        >>> pprint(config)
        {}
        >>> mock.calls_for('eprint')
        'warn: `functions` section not found in serverless.yml'

        >>> args.yes = False
        >>> args.reference = False
        >>> args.no_reference = False

        >>> mock.mock(None, 'input_query', False)
        >>> config = {'functions': {'some': {}, 'another': {}}}
        >>> ServerlessFramework("path/to/project", {}, args=args)._reference_roles(permissions, config)
        >>> pprint(config)
        {'functions': {'another': {}, 'some': {}}}
        >>> mock.calls_for('input_query')
        'Reference functions to new roles?{}', ''

        >>> mock.mock(None, 'input_query', True)
        >>> config = {'functions': {'some': {}, 'another': {}}}
        >>> ServerlessFramework("path/to/project", {}, args=args)._reference_roles(permissions, config)
        >>> pprint(config)
        {'functions': {'another': {'role': 'puresecAnotherRole'}, 'some': {'role': 'puresecSomeRole'}}}
        >>> mock.calls_for('input_query')
        'Reference functions to new roles?{}', ''
        """

        if 'functions' not in config:
            eprint("warn: `functions` section not found in serverless.yml")
            return

        if (self.args.yes or self.args.reference) or (not self.args.no_reference and input_query("Reference functions to new roles?{}", self.query_suffix)):
            for name in permissions.keys():
                if name not in config['functions']:
                    eprint("warn: `{}` not found under the `functions` section in serverless.yml", name)
                    continue
                config['functions'][name]['role'] = "puresec{}Role".format(capitalize(name))

    def _remove_old_roles(self, config, old_resources, new_resources, old_roles, new_roles):
        """
        >>> from pprint import pprint
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(ServerlessFramework, '_init_executable')

        >>> class Args:
        ...     pass
        >>> args = Args()
        >>> args.yes = True

        >>> old_roles = ['someRole']

        >>> ServerlessFramework("path/to/project", {}, args=args)._remove_old_roles({}, {}, {}, old_roles, set())

        >>> config = {'provider': {'iamRoleStatements': "some roles"}}
        >>> ServerlessFramework("path/to/project", {}, args=args)._remove_old_roles(config, {}, {}, old_roles, set())
        >>> config
        {}

        >>> config = {'provider': {'iamRoleStatements': "some roles", 'name': 'aws'}}
        >>> ServerlessFramework("path/to/project", {}, args=args)._remove_old_roles(config, {}, {}, old_roles, set())
        >>> config
        {'provider': {'name': 'aws'}}

        >>> config = {'provider': {'iamRoleStatements': "some roles"}}
        >>> ServerlessFramework("path/to/project", {}, function="some", args=args)._remove_old_roles(config, {}, {}, [], set())
        >>> config
        {'provider': {'iamRoleStatements': 'some roles'}}

        >>> old_resources = {'someRole': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['lambda.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> new_resources = {'someRole': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['lambda.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> ServerlessFramework("path/to/project", {}, args=args)._remove_old_roles({}, old_resources, new_resources, old_roles, set())
        >>> new_resources
        {}

        >>> old_resources = {'someRole': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['lambda.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> new_resources = {'someRole': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['lambda.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> new_roles = {'someRole'}
        >>> ServerlessFramework("path/to/project", {}, args=args)._remove_old_roles({}, old_resources, new_resources, old_roles, new_roles)
        >>> pprint(new_resources)
        {'someRole': {'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Action': 'sts:AssumeRole', 'Effect': 'Allow', 'Principal': {'Service': ['lambda.amazonaws.com']}}]}}, 'Type': 'AWS::IAM::Role'}}

        >>> old_resources = {'dynamodbTable': {'Type': 'AWS::DynamoDB::Table'}}
        >>> new_resources = {'dynamodbTable': {'Type': 'AWS::DynamoDB::Table'}}
        >>> ServerlessFramework("path/to/project", {}, args=args)._remove_old_roles({}, old_resources, new_resources, old_roles, set())
        >>> new_resources
        {'dynamodbTable': {'Type': 'AWS::DynamoDB::Table'}}

        >>> old_resources = {'ec2Role': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['ec2.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> new_resources = {'ec2Role': {'Type': 'AWS::IAM::Role', 'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Effect': 'Allow', 'Principal': {'Service': ['ec2.amazonaws.com']}, 'Action': 'sts:AssumeRole'}]}}}}
        >>> ServerlessFramework("path/to/project", {}, args=args)._remove_old_roles({}, old_resources, new_resources, old_roles, set())
        >>> pprint(new_resources)
        {'ec2Role': {'Properties': {'AssumeRolePolicyDocument': {'Statement': [{'Action': 'sts:AssumeRole', 'Effect': 'Allow', 'Principal': {'Service': ['ec2.amazonaws.com']}}]}}, 'Type': 'AWS::IAM::Role'}}

        >>> config = {'functions': {'some': {'role': "someRole"}}}
        >>> new_resources = {'someRole': "some role", 'anotherRole': "another role"}
        >>> ServerlessFramework("path/to/project", {}, function="some", args=args)._remove_old_roles(config, {}, new_resources, old_roles, set())
        >>> new_resources
        {'anotherRole': 'another role'}
        """

        if old_roles:
            old_roles_format = "\n".join("  - {}".format(role) for role in old_roles)
            if (self.args.yes or self.args.remove_obsolete) or (not self.args.no_remove_obsolete and input_query("These roles are now obsolete:\n{}\nWould you like to remove them?", old_roles_format)):
                # default role
                if not self.function and 'iamRoleStatements' in config.get('provider', ()):
                    del config['provider']['iamRoleStatements']
                    if not config['provider']:
                        del config['provider']
                # specific roles
                if not self.function:
                    # roles assumed for lambda
                    for resource_id, resource_config in old_resources.items():
                        if resource_config.get('Type') == 'AWS::IAM::Role':
                            # meh
                            if 'lambda.amazonaws.com' in str(resource_config.get('Properties', {}).get('AssumeRolePolicyDocument')):
                                if resource_id not in new_roles and resource_id in new_resources:
                                    del new_resources[resource_id]
                else:
                    # specified function's role (should be the only one in old roles)
                    if old_roles:
                        del new_resources[old_roles[0]]

    def _package(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(ServerlessFramework, '_init_executable')

        >>> ServerlessFramework("path/to/project", {})._package()
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: could not find serverless config in: {}', 'path/to/project/serverless.yml'
        """

        if not hasattr(self, '_serverless_package'):
            # sanity check so that we know FileNotFoundError later means Serverless is not installed
            serverless_config_path = os.path.join(self.path, "serverless.yml")
            if not os.path.exists(serverless_config_path):
                eprint("error: could not find serverless config in: {}", serverless_config_path)
                raise SystemExit(-1)

            self._serverless_package = TemporaryDirectory(prefix="puresec-")

            try:
                # Suppressing output
                subprocess.check_output([self.executable, 'package', '--package', self._serverless_package.name], cwd=self.path, stderr=subprocess.STDOUT)
            except FileNotFoundError:
                eprint("error: serverless framework not installed, run `npm install -g severless` (or use --framework-path if not globally installed)")
                raise SystemExit(-1)
            except subprocess.CalledProcessError as e:
                eprint("error: serverless package failed:\n{}", e.output.decode())
                raise SystemExit(-1)

    @property
    def _serverless_config(self):
        """
        >>> from pprint import pprint
        >>> from collections import namedtuple
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(ServerlessFramework, '_init_executable')

        >>> TemporaryDirectory = namedtuple('TemporaryDirectory', ('name',))

        >>> framework = ServerlessFramework("path/to/project", {})
        >>> framework._package = lambda: None

        >>> framework._serverless_package = TemporaryDirectory('/tmp/package')
        >>> framework._serverless_config
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: serverless package did not create serverless-state.json'

        >>> with mock.open('/tmp/package/serverless-state.json', 'w') as f:
        ...     f.write('invalid') and None
        >>> framework._serverless_config
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint') # ValueError for <=3.4, JSONDecodeError for >=3.5
        'error: invalid serverless-state.json:\\n{}', ...Error('Expecting value: line 1 column 1 (char 0)',)

        >>> with mock.open('/tmp/package/serverless-state.json', 'w') as f:
        ...     f.write('{ "x": { "y": 1 }, "z": 2 }') and None
        >>> pprint(framework._serverless_config)
        {'x': {'y': 1}, 'z': 2}
        """

        if hasattr(self, '_serverless_config_cache'):
            return self._serverless_config_cache

        self._package()
        try:
            serverless_config = open(os.path.join(self._serverless_package.name, 'serverless-state.json'), 'r', errors='replace')
        except FileNotFoundError:
            eprint("error: serverless package did not create serverless-state.json")
            raise SystemExit(-1)

        with serverless_config:
            try:
                self._serverless_config_cache = json.load(serverless_config)
            except ValueError as e:
                eprint("error: invalid serverless-state.json:\n{}", e)
                raise SystemExit(-1)

        return self._serverless_config_cache

    def get_provider_name(self):
        return self._serverless_config['service']['provider']['name']

    def get_resource_template(self):
        self._package()
        return os.path.join(self._serverless_package.name, 'cloudformation-template-update-stack.json')

    def get_default_profile(self):
        return self._serverless_config['service']['provider'].get('profile')

    def get_default_region(self):
        return self._serverless_config['service']['provider'].get('region')

    def get_function_name(self, provider_function_name):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(ServerlessFramework, '_init_executable')

        >>> framework = ServerlessFramework("path/to/project", {})

        >>> framework._serverless_config_cache = {'service': {'functions': {'otherFunction': {'name': 'other-function'}}}}
        >>> framework.get_function_name('function-name')
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        "error: could not find Serverless name for function: '{}'", 'function-name'

        >>> framework._serverless_config_cache = {'service': {'functions': {'functionName': {'name': 'function-name'}}}}
        >>> framework.get_function_name('function-name')
        'functionName'
        """

        for name, function_config in self._serverless_config['service'].get('functions', {}).items():
            if function_config['name'] == provider_function_name:
                return name

        eprint("error: could not find Serverless name for function: '{}'", provider_function_name)
        raise SystemExit(-1)

    def get_function_root(self, name):
        self._package()

        package_name = self._get_function_package_name(name)
        function_root = os.path.join(self._serverless_package.name, package_name)
        if os.path.exists(function_root):
            return function_root

        try:
            zipfile = ZipFile(os.path.join(self._serverless_package.name, "{}.zip".format(package_name)), 'r')
        except FileNotFoundError:
            eprint("error: serverless package did not create a function zip for '{}'", name)
            raise SystemExit(2)
        except BadZipFile:
            eprint("error: serverless package did not create a valid function zip for '{}'", name)
            raise SystemExit(2)

        with zipfile:
            zipfile.extractall(function_root)
        return function_root

    def _get_function_package_name(self, name):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> mock.mock(ServerlessFramework, '_init_executable')

        >>> framework = ServerlessFramework("path/to/project", {})

        >>> framework._serverless_config_cache = {'service': {'service': "serviceName"}}
        >>> framework._get_function_package_name('functionName')
        'serviceName'

        >>> framework._serverless_config_cache = {'service': {'service': "serviceName"}, 'package': {'individually': True}}
        >>> framework._get_function_package_name('functionName')
        'functionName'
        """

        if not self._serverless_config.get('package', {}).get('individually', False):
            return self._serverless_config['service']['service']
        else:
            return name

Framework = ServerlessFramework

