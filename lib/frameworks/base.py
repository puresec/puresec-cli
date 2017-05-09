from lib.utils import eprint
import abc

class Base:
    __metaclass__ = abc.ABCMeta

    def __init__(self, path, config):
        self.path = path
        self.config = config

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

    def get_resource_template(self):
        eprint("error: could not get resource template from framework '{}'", type(self).__name__)
        raise SystemExit(2)

    def get_default_profile(self):
        return None

    def get_default_region(self):
        return None

    def fix_name(self, name):
        return name

    def get_function_root(self, name):
        return None

