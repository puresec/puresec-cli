import traceback
from termcolor import colored

def dict_iterator(dict_obj, pre_list=None):
    """ Iterates through a complex dict structure and Outputs
    nested lists
    """
    if pre_list:
        pre_list = pre_list[:]
    else:
        pre_list = []

    if isinstance(dict_obj, dict):
        for key, value in dict_obj.items():
            if isinstance(value, dict):
                for d_obj in dict_iterator(value, [key] + pre_list):
                    yield d_obj
            elif isinstance(value, list) or isinstance(value, tuple):
                for v in value:
                    for d_obj in dict_iterator(v, [key] + pre_list):
                        yield d_obj
            else:
                yield pre_list + [key, value]
    else:
        yield dict_obj

def log_msg(message):
    """ Logs messages to console
    """
    print colored("PureSec: ", "blue"),
    print str(message)

def log_error(error):
    """ Logs catched exceptions / errors
    """
    print "PureSec Error: " + str(error)
