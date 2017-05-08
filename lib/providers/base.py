from .. import arguments
from ..utils import eprint
import abc
import os

class Base:
    __metaclass__ = abc.ABCMeta

    def __init__(self, path, config, resource_template=None, framework=None):
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

    def _process_function(self, name, processor, *args, **kwargs):
        root = os.path.join(self.path, self._get_function_root(name))

        for subdir, dirs, files in os.walk(root):
            for file in files:
                filename = os.path.join(subdir, file)
                with open(filename, 'rb') as file:
                    processor(
                            filename,
                            file.read(),
                            *args,
                            **kwargs
                            )

