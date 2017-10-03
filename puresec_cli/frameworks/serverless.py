from shutil import which
from tempfile import TemporaryDirectory
import abc
import json
import os
import subprocess

from puresec_cli.utils import eprint

class Serverless:
    __metaclass__ = abc.ABCMeta

    def __init__(self, path, executable='serverless'):
        self.path = path
        self.executable_name = executable or 'serverless'

    @property
    def executable(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> mock.mock(None, 'which', None)
        >>> Serverless("path/to/project").executable
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        "error: could not find framework executable: '{}', try using --framework-path", 'serverless'

        >>> mock.mock(None, 'which', "/usr/bin/serverless")
        >>> Serverless("path/to/project").executable
        '/usr/bin/serverless'
        """

        if not hasattr(self, '_executable'):
            executable = which(self.executable_name)
            if not executable:
                eprint("error: could not find framework executable: '{}', try using --framework-path", self.executable_name)
                raise SystemExit(2)

            self._executable = os.path.abspath(executable)
        return self._executable

    def __exit__(self, type, value, traceback):
        if hasattr(self, 'serverless_package'):
            self.serverless_package.cleanup()

    def package(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> Serverless("path/to/project").package()
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: could not find serverless config in: {}', 'path/to/project/serverless.yml'
        """

        if not hasattr(self, 'serverless_package'):
            # sanity check so that we know FileNotFoundError later means Serverless is not installed
            serverless_config_path = os.path.join(self.path, "serverless.yml")
            if not os.path.exists(serverless_config_path):
                eprint("error: could not find serverless config in: {}", serverless_config_path)
                raise SystemExit(-1)

            self.serverless_package = TemporaryDirectory(prefix="puresec-")

            try:
                # Suppressing output
                subprocess.check_output([self.executable, 'package', '--package', self.serverless_package.name], cwd=self.path, stderr=subprocess.STDOUT)
            except FileNotFoundError:
                eprint("error: serverless framework not installed, run `npm install -g severless` (or use --framework-path if not globally installed)")
                raise SystemExit(-1)
            except subprocess.CalledProcessError as e:
                eprint("error: serverless package failed:\n{}", e.output.decode())
                raise SystemExit(-1)

    @property
    def serverless_config(self):
        """
        >>> from pprint import pprint
        >>> from collections import namedtuple
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> TemporaryDirectory = namedtuple('TemporaryDirectory', ('name',))

        >>> serverless = Serverless("path/to/project")
        >>> serverless.package = lambda: None

        >>> serverless.serverless_package = TemporaryDirectory('/tmp/package')
        >>> serverless.serverless_config
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: serverless package did not create serverless-state.json'

        >>> with mock.open('/tmp/package/serverless-state.json', 'w') as f:
        ...     f.write('invalid') and None
        >>> serverless.serverless_config
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint') # ValueError for <=3.4, JSONDecodeError for >=3.5
        'error: invalid serverless-state.json:\\n{}', ...Error('Expecting value: line 1 column 1 (char 0)',)

        >>> with mock.open('/tmp/package/serverless-state.json', 'w') as f:
        ...     f.write('{ "x": { "y": 1 }, "z": 2 }') and None
        >>> pprint(serverless.serverless_config)
        {'x': {'y': 1}, 'z': 2}
        """

        if hasattr(self, '_serverless_config_cache'):
            return self._serverless_config_cache

        self.package()
        try:
            serverless_config = open(os.path.join(self.serverless_package.name, 'serverless-state.json'), 'r', errors='replace')
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

    def get_resource_template(self):
        self.package()
        return os.path.join(self.serverless_package.name, 'cloudformation-template-update-stack.json')

    def get_provider_name(self):
        return self.serverless_config['service']['provider']['name']

    def get_default_profile(self):
        return self.serverless_config['service']['provider'].get('profile')

    def get_default_region(self):
        return self.serverless_config['service']['provider'].get('region')

