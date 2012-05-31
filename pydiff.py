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
    try:
        lno = la.lineno
        rno = ra.lineno
    except AttributeError:
        pass
    #if isinstance(la, ast.Node):
    #if isinstance(ra, ast.Node):
    if (lno is not None) or (rno is not None):
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

    if not hasattr(l, '__len__'):
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


def ast_find_next_match(item, seq, rstart):
    c = len(seq)
    i = rstart
    while i < c:
        r, diffs = astdiff(item, seq[i])
        if r:
            return i
        i += 1
    return None


def ast_diff_zip(ls, rs):
    diffs = []
    for li, ri in izip_longest(ls, rs):
        r, idiffs = astdiff(li, ri)
        if not r:
            if idiffs != []:
                diffs.extend(idiffs)
            else:
                diffs.extend(astlineno(li, ri))
    return diffs


def astdiff_seqs(la, ra):
    diffs = []
    r = True
    #two sequences are equal if items are equal
    li = 0
    ri = 0
    lc = len(la)
    rc = len(ra)
    li_mis = 0  # if la[li] == ra[ri], then li_mis = li + 1

    while li < lc and ri < rc:
        iresult, idiffs = astdiff(la[li], ra[ri])
        if iresult:
            li += 1
            ri += 1
            li_mis = li
            continue
        r = False
        nxt = ast_find_next_match(la[li], ra, ri)
        if nxt is None:
            li += 1
            continue
        diffs.extend(ast_diff_zip(la[li_mis:li], ra[ri:nxt]))
        ri = nxt + 1
        li += 1
        li_mis = li

    diffs.extend(ast_diff_zip(la[li_mis:lc], ra[ri:rc]))

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
