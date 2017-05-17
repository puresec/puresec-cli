import abc
import os

class Base:
    __metaclass__ = abc.ABCMeta

    def __init__(self, root, config):
        self.root = root
        self.config = config

    def _walk(self, processor, *args, **kwargs):
        """
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)

        >>> processed = []
        >>> class Runtime(Base):
        ...     def processor(self, filename, file, custom_positional, custom_keyword):
        ...         processed.append((filename, file.read(), custom_positional, custom_keyword))

        >>> mock.filesystem = {'path': {'to': {'function': {
        ...     'a': True,
        ...     'b': {'c': True, 'd': True},
        ...     }}}}
        >>> with mock.open("path/to/function/a", 'w') as f:
        ...     f.write("a content") and None
        >>> with mock.open("path/to/function/b/c", 'w') as f:
        ...     f.write("c content") and None
        >>> with mock.open("path/to/function/b/d", 'w') as f:
        ...     f.write("d content") and None

        >>> runtime = Runtime('path/to/function', config={})
        >>> runtime._walk(runtime.processor, 'positional', custom_keyword='keyword')
        >>> sorted(processed)
        [('path/to/function/a', 'a content', 'positional', 'keyword'),
         ('path/to/function/b/c', 'c content', 'positional', 'keyword'),
         ('path/to/function/b/d', 'd content', 'positional', 'keyword')]
        """

        for path, dirs, files in os.walk(self.root):
            for file in files:
                filename = os.path.join(path, file)
                with open(filename, 'r', errors='replace') as file:
                    processor(filename, file, *args, **kwargs)

