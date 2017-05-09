from lib import arguments
from lib.utils import eprint
import abc

class Base:
    __metaclass__ = abc.ABCMeta

    def __init__(self, path, config, resource_template=None, framework=None):
        """
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> class Handler(Base):
        ...     pass
        >>> from lib.frameworks.base import Base as FrameworkBase
        >>> class Framework(FrameworkBase):
        ...     def get_resource_template(self):
        ...         return "path/to/resource_template"

        >>> Handler("path/to/project", config={})
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        'error: must specify either --framework or --resource-template'

        >>> Handler("path/to/project", config={}, resource_template="path/to/resource_template").resource_template
        'path/to/resource_template'
        >>> Handler("path/to/project", config={}, framework=Framework("", {})).resource_template
        'path/to/resource_template'
        >>> Handler("path/to/project", config={}, resource_template="path/to/custom_resource_template", framework=Framework("", {})).resource_template
        'path/to/custom_resource_template'
        """

        self.path = path
        self.config = config
        self.resource_template = resource_template
        self.framework = framework

        if not self.resource_template:
            if not self.framework:
                arguments.parser.print_usage()
                eprint("error: must specify either --framework or --resource-template")
                raise SystemExit(2)

            self.resource_template = self.framework.get_resource_template()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

    @abc.abstractmethod
    def process(self):
        pass

    def _get_function_root(self, name):
        """
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'input', "path/to/function")

        >>> class Handler(Base):
        ...     pass
        >>> from lib.frameworks.base import Base as FrameworkBase
        >>> class Framework(FrameworkBase):
        ...     def __init__(self, has_function_root):
        ...         self.has_function_root = has_function_root
        ...     def get_resource_template(self):
        ...         return "path/to/resource_template"
        ...     def get_function_root(self, name):
        ...         return "path/to/{}".format(name) if self.has_function_root else None

        >>> config = {}
        >>> Handler("path/to/project", config=config, framework=Framework(True))._get_function_root('function')
        'path/to/function'
        >>> config
        {}

        >>> config = {'functions': {'function': {'root': "path/to/function"}}}
        >>> Handler("path/to/project", config=config, framework=Framework(False))._get_function_root('function')
        'path/to/function'
        >>> config
        {'functions': {'function': {'root': 'path/to/function'}}}

        >>> config = {'functions': {'function': {'root': "path/to/function"}}}
        >>> Handler("path/to/project", config=config, resource_template="path/to/resource_template")._get_function_root('function')
        'path/to/function'
        >>> config
        {'functions': {'function': {'root': 'path/to/function'}}}

        >>> 'input' not in mock.calls
        True

        >>> config = {}
        >>> Handler("path/to/project", config=config, framework=Framework(False))._get_function_root('function')
        'path/to/function'
        >>> config
        {'functions': {'function': {'root': 'path/to/function'}}}

        >>> config = {}
        >>> Handler("path/to/project", config=config, resource_template="path/to/resource_template")._get_function_root('function')
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
        if not root:
            root = self.config.get('functions', {}).get(name, {}).get('root')
        # From user input
        if not root:
            root = input("Enter root directory for function '{}': {}/".format(name, self.path))
            self.config.setdefault('functions', {}).setdefault(name, {})['root'] = root

        return root

