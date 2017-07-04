from collections import defaultdict
import abc
import os

from puresec_cli import stats

class Base:
    __metaclass__ = abc.ABCMeta

    def __init__(self, root, provider):
        # {'environment': {'runtimes': {'NodejsRuntime': 2, 'PythonRuntime': 1}}}
        stats.payload['environment'].setdefault('runtimes', defaultdict(int))[type(self).__name__] += 1

        self.root = root
        self.provider = provider

    MAX_FILE_SIZE = 5 * 1024 * 1024 # 5MB

    # processor: function(filename, contents, *args, **kwargs)
    def _walk(self, processor, *args, **kwargs):
        """
        >>> from collections import namedtuple
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)

        >>> processed = []
        >>> class Runtime(Base):
        ...     def processor(self, filename, contents, custom_positional, custom_keyword):
        ...         processed.append((filename, contents, custom_positional, custom_keyword))

        >>> mock.filesystem = {'path': {'to': {'function': {
        ...     'a': True,
        ...     'b': {'c': True, 'd': True},
        ...     'e': True,
        ... }}}}
        >>> with mock.open("path/to/function/a", 'w') as f:
        ...     f.write("a content") and None
        >>> with mock.open("path/to/function/b/c", 'w') as f:
        ...     f.write("c content") and None
        >>> with mock.open("path/to/function/b/d", 'w') as f:
        ...     f.write("d content") and None

        >>> runtime = Runtime('path/to/function', None)

        >>> def stat(filename):
        ...     return namedtuple('Stat', ('st_size',))(5*1024*1024 if filename == "path/to/function/e" else 512)
        >>> mock.mock(runtime, '_stat', stat)

        >>> runtime._walk(runtime.processor, 'positional', custom_keyword='keyword')
        >>> sorted(processed)
        [('path/to/function/a', 'a content', 'positional', 'keyword'),
         ('path/to/function/b/c', 'c content', 'positional', 'keyword'),
         ('path/to/function/b/d', 'd content', 'positional', 'keyword')]
        """

        for path, dirs, filenames in os.walk(self.root):
            for filename in filenames:
                filename = os.path.join(path, filename)

                if self._stat(filename).st_size >= Base.MAX_FILE_SIZE:
                    continue

                with open(filename, 'r', errors='replace') as file:
                    processor(filename, file.read(), *args, **kwargs)

    def _stat(self, filename):
        """ Making os.stat testable again. """
        return os.stat(filename)

