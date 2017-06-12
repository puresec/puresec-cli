class PrettySet(set):
    def __repr__(self):
        if not self:
            return "set()"
        return "{{{}}}".format(', '.join(map(repr, sorted(self))))

def normalize_dict(obj):
    if isinstance(obj, set):
        return PrettySet(obj)
    elif not isinstance(obj, dict):
        return obj
    return dict((k, normalize_dict(v)) for k, v in obj.items())

