import abc

class Base:
    __metaclass__ = abc.ABCMeta

    @abc.abstractstaticmethod
    def command():
        pass

    @staticmethod
    def argument_parser_options():
        return {}

    @staticmethod
    def add_arguments(parser):
        pass

    def __init__(self, args, stats):
        self.args = args
        self.stats = stats

    @abc.abstractmethod
    def run(self):
        pass

