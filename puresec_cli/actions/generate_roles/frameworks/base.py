import abc

from puresec_cli import stats

class Base:
    __metaclass__ = abc.ABCMeta

    def __init__(self, path, config, function=None, args=None):
        stats.payload['environment']['framework'] = type(self).__name__

        self.path = path
        self.config = config
        self.function = function
        self.args = args

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

    def role_prefix(self, name):
        pass

    @property
    def result_format(self):
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

