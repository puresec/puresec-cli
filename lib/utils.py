import sys

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def deepmerge(a, b):
    for k in b:
        if k not in a:
            a[k] = b[k]
            continue
        if type(v) is dict:
            merge_dict(a[k], b[k])
        elif type(v) is set:
            a[k].update(b[k])
        else:
            raise Exception("Don't know how to merge '{}' with '{}'".format(repr(a[k]), repr(b[k])))
    return a
