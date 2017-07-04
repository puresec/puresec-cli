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

    def __init__(self, args):
        self.args = args

    @abc.abstractmethod
    def run(self):
        pass

