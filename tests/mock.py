from collections import defaultdict
from io import BytesIO, BufferedRandom, TextIOWrapper
from pprint import pformat
from tests.utils import normalize_dict, PrettySet
import os
import sys
import weakref

class Mock:
    def __init__(self, module_name):
        self.module = sys.modules[module_name]

        self.mocks = {}
        self.calls = defaultdict(list)
        self.opened = {}

        # default mocks
        self.stderr = sys.stderr
        sys.stderr = sys.stdout
        self.module.open = self.open
        if hasattr(self.module, 'os'):
            self.module.os.path.exists = self.exists
            self.module.os.walk = self.walk

    def __del__(self):
        sys.stderr = self.stderr
        for stream in self.opened.values():
            stream.close()
        for module, name in tuple(self.mocks):
            self.unmock(module, name)

    def mock(self, module, name, return_value=None):
        if (module, name) not in self.mocks:
            self.mocks[(module, name)] = getattr(module or self.module, name, None)

        self = weakref.proxy(self)
        module_name = module.__name__ if hasattr(module, '__name__') else type(module).__name__
        call_name = "{}.{}".format(module_name, name) if module else name
        def _mock(*attrs, **kwargs):
            self.calls[call_name].append((attrs, kwargs))
            return return_value(*attrs, **kwargs) if callable(return_value) else return_value

        setattr(module or self.module, name, _mock)

    def unmock(self, module, name):
        if self.mocks[(module, name)] is not None:
            setattr(module or self.module, name, self.mocks[(module, name)])
        else:
            delattr(module or self.module, name)
        del self.mocks[(module, name)]

    def calls_for(self, name):
        def pretty_object(obj):
            if hasattr(obj, '__name__'):
                return obj.__name__
            elif type(obj).__repr__ is object.__repr__:
                return type(obj).__name__
            elif isinstance(obj, dict):
                return pformat(normalize_dict(obj))
            elif isinstance(obj, set):
                return repr(PrettySet(obj))
            else:
                return repr(obj)

        for args, kwargs in self.calls[name]:
            formatted = []
            if args:
                formatted.append(', '.join(map(pretty_object, args)))
            if kwargs:
                formatted.append(', '.join("{}={}".format(k, pretty_object(v)) for k, v in sorted(kwargs.items())))
            print(', '.join(formatted))

        del self.calls[name]

    def open(self, path, mode='r', errors=None):
        stream = self.opened.get(path)
        if not stream:
            if mode[0] == 'r':
                raise FileNotFoundError(path)
            stream = self.opened[path] = BytesIO()
        stream.seek(0)
        stream = BufferedRandom(stream) if mode[-1] == 'b' else TextIOWrapper(stream)
        stream.close = stream.flush

        return stream

    def exists(self, path):
        return path in self.opened

    def walk(self, path):
        current = self.filesystem
        for part in path.split(os.path.sep):
            current = current.get(part, {})

        return self._walk(path, current)

    def _walk(self, path, current, result=None):
        if result is None:
            result = []

        dirs = []
        files = []
        for name, contents in current.items():
            if isinstance(contents, dict):
                dirs.append(name)
            else:
                files.append(name)

        result.append((path, dirs, files))
        for dir in dirs:
            self._walk(os.path.join(path, dir), current[dir], result)

        return result

