from puresec_generate_roles.lib.utils import eprint
from shutil import which
import abc
import os

class Base:
    __metaclass__ = abc.ABCMeta

    def __init__(self, path, config, executable):
        self.path = path
        self.config = config
        self.executable = executable

        self._init_executable()

    # Override this if your framework doesn't require an executable (or doesn't want to receive one)
    def _init_executable(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> class Framework(Base):
        ...     pass

        >>> Framework("path/to/project", {}, None)
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        'error: no default framework executable, please supply with --framework-path'

        >>> mock.mock(None, 'which', None)
        >>> Framework("path/to/project", {}, 'serverless')
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        "error: could not find framework executable: 'serverless', try using --framework-path"

        >>> mock.mock(None, 'which', "/usr/bin/serverless")
        >>> Framework("path/to/project", {}, 'serverless').executable
        '/usr/bin/serverless'
        """

        if not self.executable:
            eprint("error: no default framework executable, please supply with --framework-path")
            raise SystemExit(2)

        executable = which(self.executable)
        if not executable:
            eprint("error: could not find framework executable: '{}', try using --framework-path".format(self.executable))
            raise SystemExit(2)

        self.executable = os.path.abspath(executable)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

    def get_format(self):
        pass

    def get_provider_name(self):
        pass

    def get_resource_template(self):
        pass

    def get_default_profile(self):
        pass

    def get_default_region(self):
        pass

    def get_function_name(self, name):
        return name

    def get_function_root(self, name):
        pass

