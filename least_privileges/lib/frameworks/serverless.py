from lib.frameworks.base import Base
from lib.utils import eprint
from subprocess import call
from tempfile import NamedTemporaryFile, TemporaryDirectory
from zipfile import ZipFile, BadZipFile
import os
import re
import yaml

class ServerlessFramework(Base):
    def __init__(self, path, config):
        """
        >>> from pprint import pprint
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> ServerlessFramework("path/to/project", config={})
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: could not find serverless config in: path/to/project/serverless.yml'

        >>> mock.open("path/to/project/serverless.yml", 'w').close()
        >>> def NamedTemporaryFile(**kwargs):
        ...     file = mock.open("/tmp/serverless-config.yml", 'w')
        ...     file.buffer.name = "/tmp/serverless-config.yml"
        ...     return file
        >>> mock.mock(None, 'NamedTemporaryFile', NamedTemporaryFile)

        >>> def call(*args, **kwargs):
        ...     raise FileNotFoundError()
        >>> mock.mock(None, 'call', call)
        >>> ServerlessFramework("path/to/project", config={})
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('call')
        ['serverless', 'dumpconfig', '-o', '/tmp/serverless-config.yml'], cwd='path/to/project'
        >>> mock.calls_for('eprint')
        'error: serverless framework not installed'

        >>> mock.mock(None, 'call', 1)
        >>> ServerlessFramework("path/to/project", config={})
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('call')
        ['serverless', 'dumpconfig', '-o', '/tmp/serverless-config.yml'], cwd='path/to/project'
        >>> mock.calls_for('eprint')
        'error: serverless dumpconfig failed'

        >>> with mock.open("/tmp/serverless-config.yml", 'w') as f:
        ...     f.write('''
        ... x:
        ...   y: 1
        ...   z: 2''') and None

        >>> mock.mock(None, 'call', 0)
        >>> pprint(ServerlessFramework("path/to/project", config={}).serverless_config)
        {'x': {'y': 1, 'z': 2}}
        >>> mock.calls_for('call')
        ['serverless', 'dumpconfig', '-o', '/tmp/serverless-config.yml'], cwd='path/to/project'
        """

        super().__init__(path, config)

        # sanity check so that we know FileNotFoundError later means Serverless is not installed
        serverless_config_path = os.path.join(self.path, "serverless.yml")
        if not os.path.exists(serverless_config_path):
            eprint("error: could not find serverless config in: {}".format(serverless_config_path))
            raise SystemExit(-1)

        with NamedTemporaryFile(prefix="least-privileges-", suffix='.yml') as serverless_config:
            try:
                result = call(['serverless', 'dumpconfig', '-o', serverless_config.name], cwd=self.path)
            except FileNotFoundError:
                eprint("error: serverless framework not installed")
                raise SystemExit(-1)

            if result != 0:
                eprint("error: serverless dumpconfig failed")
                raise SystemExit(-1)

            try:
                self.serverless_config = yaml.load(serverless_config)
            except yaml.YAMLError as e:
                eprint("error: invalid serverless.yml:\n{}".format(e))
                raise SystemExit(-1)

    def __exit__(self, type, value, traceback):
        super().__exit__(type, value, traceback)

        if hasattr(self, 'serverless_package'):
            self.serverless_package.cleanup()

    def _unpack(self):
        if not hasattr(self, 'serverless_package'):
            self.serverless_package = TemporaryDirectory(prefix="least-privileges-")

            try:
                result = call(['serverless', 'package', '--package', self.serverless_package.name], cwd=self.path)
            except FileNotFoundError:
                eprint("error: serverless framework not installed")
                raise SystemExit(-1)

            if result != 0:
                eprint("error: serverless package failed")
                raise SystemExit(result)

    def get_resource_template(self):
        self._unpack()
        return os.path.join(self.serverless_package.name, "cloudformation-template-update-stack.json")

    def get_default_profile(self):
        return self.serverless_config.get('provider', {}).get('profile')

    def get_default_region(self):
        return self.serverless_config.get('provider', {}).get('region')

    NAME_PATTERN = re.compile(r"[^-]+-[^-]+-(.*)")
    def fix_function_name(self, name):
        match = ServerlessFramework.NAME_PATTERN.match(name)
        if not match:
            eprint("error: serverless did not create a valid name: '{}'".format(name))
            raise SystemExit(-1)
        return match.group(1)

    def get_function_root(self, name):
        self._unpack()

        function_root = os.path.join(self.serverless_package.name, name)
        if os.path.exists(function_root):
            return function_root

        try:
            zipfile = ZipFile(os.path.join(self.serverless_package.name, "{}.zip".format(name)), 'r')
        except FileNotFoundError:
            eprint("error: serverless package did not create a function zip for '{}'".format(name))
            raise SystemExit(2)
        except BadZipFile:
            eprint("error: serverless package did not create a valid function zip for '{}'".format(name))
            raise SystemExit(2)

        with zipfile:
            zipfile.extractall(function_root)
        return function_root

Framework = ServerlessFramework

