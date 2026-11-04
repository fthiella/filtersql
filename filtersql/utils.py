# -*- coding: utf-8 -*-
"""
SQL Backend Library for AI, Datatables and Frontend Apps
"""
import re

# parse Datatable Args

_DT_SCALARS = ('draw', 'start', 'length', '_')
_DT_KEY_RE = re.compile(
    r'^(\w+)(?:\[(\w+)\])(?:\[(\w+)\])?(?:\[(\w+)\])?$'
)


_MISSING = object()


def _int_str(v):
    # ASCII digits only: str.isdigit() is also true for '²' or '٣', which
    # int() then rejects with ValueError.
    if v.isascii() and v.isdigit():
        return int(v)
    return v


def parseDatatableArgs(args):
    """
    Turn DataTables' flat query args (``columns[0][search][value]=x``) into
    nested dicts (``{'columns': {0: {'search': {'value': 'x'}}}}``).

    `args` comes straight from the client, so this function does not raise on
    odd input (non-string keys, malformed or conflicting keys): keys that do not match the bracket syntax, or that conflict
    with an earlier key (``a[0][b]=1`` followed by ``a[0][b][c]=2``), are
    skipped and the first value wins.
    """
    p = {}
    for a in args:
        if not isinstance(a, str):
            continue
        if a in _DT_SCALARS:
            p[a] = args.get(a)
            continue

        m = _DT_KEY_RE.match(a)
        if not m:
            continue

        path = [_int_str(g) for g in m.groups() if g is not None]
        node = p
        for k in path[:-1]:
            child = node.get(k, _MISSING)
            if child is _MISSING:
                child = node[k] = {}
            if not isinstance(child, dict):
                break  # an earlier key made this a leaf: conflict, skip
            node = child
        else:
            if not isinstance(node.get(path[-1]), dict):
                node[path[-1]] = args.get(a)

    return p
