import re
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

PARANTHASES_PATTERN = re.compile(r"[\(\)]")
def get_inner_parentheses(value):
    """
    >>> get_inner_parentheses('(hello)')
    'hello'
    >>> get_inner_parentheses('(he(l)lo)')
    'he(l)lo'
    >>> get_inner_parentheses('(h(e(l)l)o)')
    'h(e(l)l)o'
    >>> get_inner_parentheses('he(llo)there')
    'llo'
    >>> get_inner_parentheses('(he(llo)')
    >>> get_inner_parentheses('hello)')
    >>> get_inner_parentheses(')hel((lo)')
    """
    start = None
    opens = 0
    for match in PARANTHASES_PATTERN.finditer(value):
        if match.group() == '(':
            if start is None:
                start = match.span()[1]
            opens += 1
        elif match.group() == ')':
            opens -= 1
            if opens == 0:
                return value[start:match.span()[0]]
            elif opens < 0:
                return None
    return None

