from utils import eprint
import abc

class Base:
    __metaclass__ = abc.ABCMeta

    def __init__(self, code_path, config):
        self.code_path = code_path
        self.config = config

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        pass

    def get_resource_template(self):
        eprint("ERROR: Could not get resource template from framework {}.", type(self).__name__)
        raise SystemExit(-2)

    def get_default_profile(self):
        return None

    def get_default_region(self):
        return None

    def get_function_root(self, name):
        return None

