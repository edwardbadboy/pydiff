#!/usr/bin/env python
from compiler import transformer
from compiler import ast
from pprint import pprint
from itertools import izip_longest
import sys

#import rpdb2
#rpdb2.start_embedded_debugger('123456')


def astlineno(la, ra):
    lno = None
    rno = None
    if hasattr(la, 'ast_child_lineno_found'):
        return True
    if hasattr(ra, 'ast_child_lineno_found'):
        return True
    if isinstance(la, ast.Node):
        try:
            lno = la.lineno
        except AttributeError:
            pass
    if isinstance(ra, ast.Node):
        try:
            rno = ra.lineno
        except AttributeError:
            pass
    if (lno is not None) or (rno is not None):
        try:
            la.ast_child_lineno_found = True
            ra.ast_child_lineno_found = True
        except AttributeError:
            pass
        return [((lno, repr(la)), (rno, repr(ra)))]
    return []


def is_map_kind(m):
    try:
        for k in m.iterkeys():
            m[k]
            break
    except AttributeError:
        return False

    return True


def is_seq_kind(l):
    try:
        for i in l:
            break
    except TypeError:
        return False

    return True


def astdiff_objects(la, ra):
    diffs = []
    r = True
    # two objects are equal if attributs are equal
    for lk, rk in izip_longest(sorted(la.__dict__.keys()),
                               sorted(ra.__dict__.keys())):
        if lk != rk:
            r = False
            break
        if lk == 'lineno' and rk == 'lineno':
            continue
        lattr = getattr(la, lk)
        rattr = getattr(ra, rk)
        attrresult, attrdiffs = astdiff(lattr, rattr)
        if not attrresult:
            if attrdiffs != []:
                diffs.extend(attrdiffs)
            r = False
    if (not r) and (diffs == []):
        diffs.extend(astlineno(la, ra))
    return r, diffs


def astdiff_maps(la, ra):
    diffs = []
    r = True
    #two mappings are equal if items are equal
    lkeys = sorted(la.keys())
    rkeys = sorted(ra.keys())
    for lk, rk in izip_longest(lkeys, rkeys):
        if lk != rk:
            r = False
            break
        iresult, idiffs = astdiff(la[lk], ra[rk])
        if not iresult:
            if idiffs != []:
                diffs.extend(idiffs)
            r = False
    if (not r) and (diffs == []):
        diffs.extend(astlineno(la, ra))
    return r, diffs


def astdiff_seqs(la, ra):
    diffs = []
    r = True
    #two sequences are equal if items are equal
    for li, ri in izip_longest(la, ra):
        iresult, idiffs = astdiff(li, ri)
        if not iresult:
            if idiffs != []:
                diffs.extend(idiffs)
            r = False
    if (not r) and (diffs == []):
        diffs.extend(astlineno(la, ra))
    return r, diffs


def astdiff(la, ra):
    # compare strings
    if isinstance(la, str) and isinstance(ra, str):
        return la == ra, []

    # compare objects
    if hasattr(la, '__dict__') and hasattr(ra, '__dict__'):
        return astdiff_objects(la, ra)

    # compare mapping obejcts
    if is_map_kind(la) and is_map_kind(ra):
        return astdiff_maps(la, ra)

    # compare sequences
    if is_seq_kind(la) and is_seq_kind(ra):
        return astdiff_seqs(la, ra)

    # compare other built-in type instance: int, float, ...
    return la == ra, []


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.stderr.write('Usage: %s file1 file2\n' % sys.argv[0])
        exit(1)

    lf = sys.argv[1]
    rf = sys.argv[2]

    la = transformer.parseFile(lf)
    ra = transformer.parseFile(rf)

    r, diffs = astdiff(la, ra)
    pprint(r)
    pprint(diffs)
