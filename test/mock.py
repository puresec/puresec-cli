from pprint import pprint
from io import BytesIO, BufferedRandom, TextIOWrapper
from functools import partial
import os
import sys

class Mock:
    def __init__(self, module_name):
        self.module = sys.modules[module_name]

        self.calls = {}
        self.opened = {}

        # default mocks
        self.module.open = self.open
        if hasattr(self.module, 'os'):
            self.module.os.walk = self.walk

    def mock(self, module, name, return_value=None):
        setattr(
                module or self.module,
                name,
                partial(self._mock, "{}.{}".format(module.__name__, name) if module else name, return_value)
                )

    def called(self, name, *args, **kwargs):
        return self.calls[name] == (args, kwargs)

    def _mock(self, name, return_value, *attrs, **kwargs):
        self.calls[name] = (attrs, kwargs)
        return return_value

    def open(self, path, mode='r'):
        stream = self.opened.get(path)
        if not stream:
            if mode[0] == 'r':
                raise FileNotFoundError(path)
            stream = self.opened[path] = BytesIO()
        stream.seek(0)
        stream = BufferedRandom(stream) if mode[-1] == 'b' else TextIOWrapper(stream)
        stream.close = stream.flush

        return stream

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
            if type(contents) is dict:
                dirs.append(name)
            else:
                files.append(name)

        result.append((path, dirs, files))
        for dir in dirs:
            self._walk(os.path.join(path, dir), current[dir], result)

        return result

    def __del__(self):
        for stream in self.opened.values():
            stream.close()

