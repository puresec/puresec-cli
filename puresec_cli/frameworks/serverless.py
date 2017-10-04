from shutil import which
from tempfile import TemporaryDirectory
import abc
import json
import os
import subprocess

from puresec_cli.utils import eprint

class Serverless:
    __metaclass__ = abc.ABCMeta

    def __init__(self, path, args=None):
        self.path = path
        self.args = args

    def __exit__(self, type, value, traceback):
        if hasattr(self, '_package'):
            self._package.cleanup()

    @property
    def serverless_package(self):
        if self.args.framework_output:
            return self.args.framework_output

        if not hasattr(self, '_package'):
            # sanity check so that we know FileNotFoundError later means Serverless is not installed
            serverless_config_path = os.path.join(self.path, "serverless.yml")
            if not os.path.exists(serverless_config_path):
                eprint("error: could not find serverless config in: {}", serverless_config_path)
                raise SystemExit(-1)

            self._package = TemporaryDirectory(prefix="puresec-serverless-package-")

            try:
                # Suppressing output
                subprocess.check_output(['serverless', 'package', '--package', self._package.name], cwd=self.path, stderr=subprocess.STDOUT)
            except FileNotFoundError:
                eprint("error: serverless framework not installed, run `npm install -g severless` (or use --framework-path if not globally installed)")
                raise SystemExit(-1)
            except subprocess.CalledProcessError as e:
                eprint("error: serverless package failed:\n{}", e.output.decode())
                raise SystemExit(-1)

        return self._package.name

    @property
    def serverless_config(self):
        """
        >>> from pprint import pprint
        >>> from collections import namedtuple
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> TemporaryDirectory = namedtuple('TemporaryDirectory', ('name',))
        >>> Args = namedtuple('Args', ('framework_output',))

        >>> serverless = Serverless("path/to/project", Args(None))
        >>> serverless._package = TemporaryDirectory('/tmp/package')
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

        try:
            serverless_config = open(os.path.join(self.serverless_package, 'serverless-state.json'), 'r', errors='replace')
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
        return os.path.join(self.serverless_package, 'cloudformation-template-update-stack.json')

    def get_provider_name(self):
        return self.serverless_config['service']['provider']['name']

    def get_default_profile(self):
        return self.serverless_config['service']['provider'].get('profile')

    def get_default_region(self):
        return self.serverless_config['service']['provider'].get('region')

