from zipfile import ZipFile, BadZipFile
from tempfile import TemporaryDirectory
import os

from puresec_cli.actions.generate_roles.frameworks.base import Base
from puresec_cli.frameworks.serverless import Serverless
from puresec_cli.utils import eprint, capitalize

class ServerlessFramework(Serverless, Base):
    def __init__(self, path, config, function=None, args=None):
        Base.__init__(
            self,
            path, config,
            function=function,
            args=args,
        )
        Serverless.__init__(
            self,
            path,
            args=args,
        )

    def __exit__(self, type, value, traceback):
        Base.__exit__(self, type, value, traceback)
        Serverless.__exit__(self, type, value, traceback)

        if hasattr(self, 'functions_output'):
            self.functions_output.cleanup()

    def role_prefix(self, name):
        return self.serverless_config['service']['service']

    @property
    def result_format(self):
        return '.yaml'

    def get_function_name(self, provider_function_name):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> framework = ServerlessFramework("path/to/project", {})

        >>> framework._serverless_config_cache = {'service': {'functions': {'otherFunction': {'name': 'other-function'}}}}
        >>> framework.get_function_name('function-name')
        'function-name'
        >>> mock.calls_for('eprint')
        "warn: could not find Serverless name for function: '{}'", 'function-name'

        >>> framework._serverless_config_cache = {'service': {'functions': {'functionName': {'name': 'function-name'}}}}
        >>> framework.get_function_name('function-name')
        'functionName'
        """

        for name, function_config in self.serverless_config['service'].get('functions', {}).items():
            if function_config['name'] == provider_function_name:
                return name

        eprint("warn: could not find Serverless name for function: '{}'", provider_function_name)

    def get_function_root(self, name):
        if not hasattr(self, 'functions_output'):
            self.functions_output = TemporaryDirectory("puresec-serverless-functions-")

        package_name = self._get_function_package_name(name)
        function_root = os.path.join(self.functions_output.name, package_name)
        if os.path.exists(function_root):
            return function_root

        try:
            zipfile = ZipFile(os.path.join(self.serverless_package, "{}.zip".format(package_name)), 'r')
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

        >>> framework = ServerlessFramework("path/to/project", {})

        >>> framework._serverless_config_cache = {'service': {'service': "serviceName"}}
        >>> framework._get_function_package_name('functionName')
        'serviceName'

        >>> framework._serverless_config_cache = {'service': {'service': "serviceName"}, 'package': {'individually': True}}
        >>> framework._get_function_package_name('functionName')
        'functionName'
        """

        if not self.serverless_config.get('package', {}).get('individually', False):
            return self.serverless_config['service']['service']
        else:
            return name

Framework = ServerlessFramework

