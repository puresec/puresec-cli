from puresec_cli.utils import eprint
from puresec_cli import stats
import abc

class Base:
    __metaclass__ = abc.ABCMeta

    def __init__(self, path, config, resource_template=None, runtime=None, framework=None, function=None, args=None):
        """
        >>> class Provider(Base):
        ...     pass
        >>> from puresec_cli.actions.generate_roles.frameworks.base import Base as FrameworkBase
        >>> class Framework(FrameworkBase):
        ...     def _init_executable(self): pass
        ...     def get_resource_template(self):
        ...         return "path/to/resource_template"

        >>> Provider("path/to/project", config={}).resource_template

        >>> Provider("path/to/project", config={}, resource_template="path/to/resource_template").resource_template
        'path/to/resource_template'
        >>> Provider("path/to/project", config={}, framework=Framework("", {}, 'ls')).resource_template
        'path/to/resource_template'
        >>> Provider("path/to/project", config={}, resource_template="path/to/custom_resource_template", framework=Framework("", {}, executable=None)).resource_template
        'path/to/custom_resource_template'
        """

        stats.payload['environment']['provider'] = type(self).__name__

        self.path = path
        self.config = config
        self.resource_template = resource_template
        self.runtime = runtime
        self.framework = framework
        self.function = function
        self.args = args

        if not self.resource_template and self.framework:
            self.resource_template = self.framework.get_resource_template()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

    @abc.abstractmethod
    def process(self):
        pass

    @abc.abstractproperty
    def permissions(self):
        pass

    @abc.abstractproperty
    def result(self):
        pass

    def runtimes(self):
        """ Returns which runtimes were used and how many times. """
        return {}

    def _get_function_root(self, name):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'input', "path/to/function")

        >>> class Provider(Base):
        ...     pass
        >>> from puresec_cli.actions.generate_roles.frameworks.base import Base as FrameworkBase
        >>> class Framework(FrameworkBase):
        ...     def __init__(self, has_function_root):
        ...         self.has_function_root = has_function_root
        ...     def get_resource_template(self):
        ...         return "path/to/resource_template"
        ...     def get_function_root(self, name):
        ...         return "path/to/{}".format(name) if self.has_function_root else None

        >>> config = {}
        >>> Provider("path/to/project", config=config, framework=Framework(True))._get_function_root('function')
        'path/to/function'
        >>> config
        {}

        >>> config = {'functions': {'function': {'root': "path/to/function"}}}
        >>> Provider("path/to/project", config=config, framework=Framework(False))._get_function_root('function')
        'path/to/function'
        >>> config
        {'functions': {'function': {'root': 'path/to/function'}}}

        >>> config = {'functions': {'function': {'root': "path/to/function"}}}
        >>> Provider("path/to/project", config=config, resource_template="path/to/resource_template")._get_function_root('function')
        'path/to/function'
        >>> config
        {'functions': {'function': {'root': 'path/to/function'}}}

        >>> 'input' not in mock.calls
        True

        >>> config = {}
        >>> Provider("path/to/project", config=config, framework=Framework(False))._get_function_root('function')
        'path/to/function'
        >>> config
        {'functions': {'function': {'root': 'path/to/function'}}}

        >>> config = {}
        >>> Provider("path/to/project", config=config, resource_template="path/to/resource_template")._get_function_root('function')
        'path/to/function'
        >>> config
        {'functions': {'function': {'root': 'path/to/function'}}}

        >>> 'input' in mock.calls
        True
        """

        root = None
        # From framework
        if self.framework:
            root = self.framework.get_function_root(name)
        # From config
        if root is None:
            root = self.config.get('functions', {}).get(name, {}).get('root')
        # From user input
        if root is None:
            root = input("Enter root directory for function '{}': {}/".format(name, self.path))
            self.config.setdefault('functions', {}).setdefault(name, {})['root'] = root

        return root

