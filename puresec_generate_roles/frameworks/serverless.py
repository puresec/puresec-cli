from puresec_generate_roles.frameworks.base import Base
from puresec_generate_roles.utils import eprint
from subprocess import Popen, PIPE, STDOUT
from tempfile import TemporaryDirectory
from zipfile import ZipFile, BadZipFile
import json
import os
import re

class ServerlessFramework(Base):
    def __init__(self, path, config, executable):
        if not executable:
            executable = 'serverless' # from environment (PATH)

        super().__init__(path, config, executable)

    def __exit__(self, type, value, traceback):
        super().__exit__(type, value, traceback)

        if hasattr(self, '_serverless_package'):
            self._serverless_package.cleanup()

    def _package(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> ServerlessFramework("path/to/project", {}, executable="ls")._package()
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: could not find serverless config in: path/to/project/serverless.yml'
        """

        if not hasattr(self, '_serverless_package'):
            # sanity check so that we know FileNotFoundError later means Serverless is not installed
            serverless_config_path = os.path.join(self.path, "serverless.yml")
            if not os.path.exists(serverless_config_path):
                eprint("error: could not find serverless config in: {}".format(serverless_config_path))
                raise SystemExit(-1)

            self._serverless_package = TemporaryDirectory(prefix="puresec-generate-roles-")

            try:
                process = Popen([self.executable, 'package', '--package', self._serverless_package.name], cwd=self.path, stdout=PIPE, stderr=STDOUT)
            except FileNotFoundError:
                eprint("error: serverless framework not installed, try using --framework-path")
                raise SystemExit(-1)

            result = process.wait()
            if result != 0:
                output, _ = process.communicate()
                eprint("error: serverless package failed:\n{}".format(output.decode()))
                raise SystemExit(result)

    @property
    def _serverless_config(self):
        """
        >>> from pprint import pprint
        >>> from collections import namedtuple
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> TemporaryDirectory = namedtuple('TemporaryDirectory', ('name',))

        >>> framework = ServerlessFramework("path/to/project", {}, executable="ls")
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
        >>> mock.calls_for('eprint')
        'error: invalid serverless-state.json:\\nExpecting value: line 1 column 1 (char 0)'

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
                eprint("error: invalid serverless-state.json:\n{}".format(e))
                raise SystemExit(-1)

        return self._serverless_config_cache

    @property
    def format(self):
        return 'yaml'
        pass

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
        >>> framework = ServerlessFramework("path/to/project", {}, executable="ls")

        >>> framework._serverless_config_cache = {'service': {'functions': {'otherFunction': {'name': 'other-function'}}}}
        >>> framework.get_function_name('function-name')
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        "error: could not find Serverless name for function: 'function-name'"

        >>> framework._serverless_config_cache = {'service': {'functions': {'functionName': {'name': 'function-name'}}}}
        >>> framework.get_function_name('function-name')
        'functionName'
        """

        for name, function_config in self._serverless_config['service'].get('functions', {}).items():
            if function_config['name'] == provider_function_name:
                return name

        eprint("error: could not find Serverless name for function: '{}'".format(provider_function_name))
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
            eprint("error: serverless package did not create a function zip for '{}'".format(name))
            raise SystemExit(2)
        except BadZipFile:
            eprint("error: serverless package did not create a valid function zip for '{}'".format(name))
            raise SystemExit(2)

        with zipfile:
            zipfile.extractall(function_root)
        return function_root

    def _get_function_package_name(self, name):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')
        >>> framework = ServerlessFramework("path/to/project", {}, executable="ls")

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

