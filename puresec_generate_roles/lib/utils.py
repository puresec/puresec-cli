import sys

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def deepmerge(a, b):
    """
    >>> from pprint import pprint

    >>> pprint(deepmerge(
    ...     {'a': {'x': 1}},
    ...     {'a': {'y': 2}, 'b': 3}
    ...     ))
    {'a': {'x': 1, 'y': 2}, 'b': 3}

    >>> pprint(deepmerge(
    ...     {'a': {'y': 2}, 'b': 3},
    ...     {'a': {'x': 1}}
    ...     ))
    {'a': {'x': 1, 'y': 2}, 'b': 3}

    >>> pprint(deepmerge(
    ...     {'a': {1, 2, 3}, 'b': {'c': {1, 2, 3}}},
    ...     {'a': {3, 4, 5}, 'b': {'c': {3, 4, 5}}}
    ...     ))
    {'a': {1, 2, 3, 4, 5}, 'b': {'c': {1, 2, 3, 4, 5}}}

    >>> pprint(deepmerge(
    ...     {'a': 1, 'b': {'c': 2}},
    ...     {'a': 1, 'b': {'c': 2}}
    ...     ))
    {'a': 1, 'b': {'c': 2}}

    >>> deepmerge(
    ...     {'a': 1},
    ...     {'a': 2}
    ...     )
    Traceback (most recent call last):
    Exception: Do not know how to merge `1` with `2`

    >>> deepmerge(
    ...     {'a': {'b': 1}},
    ...     {'a': {'b': 2}}
    ...     )
    Traceback (most recent call last):
    Exception: Do not know how to merge `1` with `2`

    >>> deepmerge(
    ...     {'a': {'b': 1}},
    ...     {'a': {2}}
    ...     )
    Traceback (most recent call last):
    Exception: Do not know how to merge `{'b': 1}` with `{2}`

    >>> deepmerge(
    ...     {'a': {'b': {'c': 1}}},
    ...     {'a': {'b': {2}}}
    ...     )
    Traceback (most recent call last):
    Exception: Do not know how to merge `{'c': 1}` with `{2}`
    """

    for k in b:
        if k not in a:
            a[k] = b[k]
            continue
        if type(a[k]) is not type(b[k]):
            raise Exception("Do not know how to merge `{}` with `{}`".format(repr(a[k]), repr(b[k])))
        if isinstance(a[k], dict):
            deepmerge(a[k], b[k])
        elif isinstance(a[k], set):
            a[k].update(b[k])
        else:
            if a[k] != b[k]:
                raise Exception("Do not know how to merge `{}` with `{}`".format(repr(a[k]), repr(b[k])))
    return a

