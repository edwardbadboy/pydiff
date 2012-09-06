#!/usr/bin/env python
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#

from getopt import getopt
from compiler import transformer
from pprint import pprint
from itertools import izip_longest
import sys

# global option: if we should compare docstrings
_diffdoc = False


# A cache for differences of syntax nodes
class dCache(object):
    def __init__(self):
        self.c = {}

    def lookup(self, la, ra):
        try:
            diff = self.c[(id(la), id(ra))]
        except KeyError:
            diff = []
        return diff

    def update(self, la, ra, diff):
        if (diff != []) and ((id(la), id(ra)) not in self.c):
            self.c[(id(la), id(ra))] = diff
        return


_dc = dCache()


# taken from PEP 257
# trim tabs and spaces in the docstrings
def trimdocstring(docstring):
    if not docstring:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxint
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxint:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)


# figure out the line numbers of la and ra
def astlineno(la, ra, lpno=None, rpno=None):
    lno = None
    rno = None
    try:
        lno = la.lineno
        rno = ra.lineno
    except AttributeError:
        pass
    if lno is None:
        lno = lpno
    if rno is None:
        rno = rpno
    if (lno is not None) or (rno is not None):
        return [((lno, repr(la)), (rno, repr(ra)))]
    return []


# can m be treated like a mapping object
def is_map_kind(m):
    try:
        for k in m.iterkeys():
            m[k]
            break
    except AttributeError:
        return False

    return True


# can l be treated like a sequence (list)
def is_seq_kind(l):
    try:
        for i in l:
            break
    except TypeError:
        return False

    if not hasattr(l, '__len__'):
        return False

    return True


# get differences between syntax nodes
def astdiff_objects(la, ra, lno=None, rno=None):
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
        if (not _diffdoc) and (lk == 'doc' and rk == 'doc'):
            continue
        lattr = getattr(la, lk)
        rattr = getattr(ra, rk)
        if lk == 'doc':
            lattr = trimdocstring(lattr)
        if rk == 'doc':
            rattr = trimdocstring(rattr)
        attrresult, attrdiffs = astdiff(lattr, rattr, lno, rno)
        if not attrresult:
            if attrdiffs != []:
                diffs.extend(attrdiffs)
            r = False
    if (not r) and (diffs == []):
        di = astlineno(la, ra, lno, rno)
        diffs.extend(di)
    _dc.update(la, ra, diffs)
    return r, diffs


# get differences between mapping objects
def astdiff_maps(la, ra, lno=None, rno=None):
    diffs = []
    r = True
    # two mappings are equal if items are equal
    lkeys = sorted(la.keys())
    rkeys = sorted(ra.keys())
    for lk, rk in izip_longest(lkeys, rkeys):
        if lk != rk:
            r = False
            break
        iresult, idiffs = astdiff(la[lk], ra[rk], lno, rno)
        if not iresult:
            if idiffs != []:
                diffs.extend(idiffs)
            r = False
    if (not r) and (diffs == []):
        di = astlineno(la, ra, lno, rno)
        diffs.extend(di)
    _dc.update(la, ra, diffs)
    return r, diffs


# find the next same element(same is in terms of astdiff) in the sequence
def ast_find_next_match(item, seq, rstart, lno=None, rno=None):
    c = len(seq)
    i = rstart
    while i < c:
        r, diffs = astdiff(item, seq[i], lno, rno)
        if r:
            return i
        i += 1
    return None


# zip two sequence with astdiff
def ast_diff_zip(ls, rs, lno=None, rno=None):
    def extractLineNO(subject, lineNO):
        l = None
        try:
            l = str(subject.lineno) + ' +'
        except AttributeError:
            l = str(lineNO) + ' + -'
        return l

    diffs = []
    preli = None
    preri = None
    for li, ri in izip_longest(ls, rs):
        lno1 = lno
        rno1 = rno
        if li is None:
            lno1 = extractLineNO(preli, lno)
        else:
            preli = li
        if ri is None:
            rno1 = extractLineNO(preri, rno)
        else:
            preri = ri
        r, idiffs = astdiff(li, ri, lno1, rno1)
        if not r:
            if idiffs != []:
                diffs.extend(idiffs)
            else:
                di = astlineno(li, ri, lno1, rno1)
                diffs.extend(di)
    return diffs


# get differences between sequences.
# usually the sequences are children nodes of a Stmt Node.
# Stmt Node represent a block of statements, its children
# are statements in the block. So the function must deal with
# insertion, deletion and modification of the elements.
def astdiff_seqs(la, ra, lno=None, rno=None):
    diffs = []
    r = True
    # two sequences are equal if items are equal
    li = 0
    ri = 0
    lc = len(la)
    rc = len(ra)
    li_mis = 0  # if la[li] == ra[ri], then li_mis = li + 1

    while li < lc and ri < rc:
        if hasattr(la[li], 'lineno'):
            if la[li].lineno is not None:
                lno = la[li].lineno
        if hasattr(ra[ri], 'lineno'):
            if ra[ri].lineno is not None:
                rno = ra[ri].lineno
        iresult, idiffs = astdiff(la[li], ra[ri], lno, rno)
        if iresult:
            li += 1
            ri += 1
            li_mis = li
            continue
        r = False

        while (li < lc):
            nxt = ast_find_next_match(la[li], ra, ri, lno, rno)
            if nxt is not None:
                if hasattr(la[li], 'lineno'):
                    if la[li].lineno is not None:
                        lno = la[li].lineno
                if hasattr(ra[nxt], 'lineno'):
                    if ra[nxt].lineno is not None:
                        rno = ra[nxt].lineno
                diffs.extend(ast_diff_zip(la[li_mis:li], ra[ri:nxt], lno, rno))
                ri = nxt + 1
                li += 1
                li_mis = li
                break
            li += 1

    if(lc != rc):
        r = False

    diffs.extend(ast_diff_zip(la[li_mis:lc], ra[ri:rc], lno, rno))

    if (not r) and (diffs == []):
        di = astlineno(la, ra, lno, rno)
        diffs.extend(di)
    _dc.update(la, ra, diffs)
    return r, diffs


# get differences between builtin objects like int, float...
def astdiff_builtin(la, ra, lno=None, rno=None):
    if la == ra:
        return True, []
    diffs = []
    if (lno is not None) or (rno is not None):
        diffs = [((lno, la), (rno, ra))]
    return False, diffs


# get differences between two Abstract Syntax Trees
def astdiff(la, ra, lno=None, rno=None):
    # inspect the difference cache
    di = _dc.lookup(la, ra)
    if di != []:
        return False, di

    if hasattr(la, 'lineno'):
        if la.lineno is not None:
            lno = la.lineno
    if hasattr(ra, 'lineno'):
        if ra.lineno is not None:
            rno = ra.lineno

    # compare strings
    if isinstance(la, str) and isinstance(ra, str):
        return astdiff_builtin(la, ra, lno, rno)

    # compare objects
    if hasattr(la, '__dict__') and hasattr(ra, '__dict__'):
        return astdiff_objects(la, ra, lno, rno)

    # compare mapping obejcts
    if is_map_kind(la) and is_map_kind(ra):
        return astdiff_maps(la, ra, lno, rno)

    # compare sequences
    if is_seq_kind(la) and is_seq_kind(ra):
        return astdiff_seqs(la, ra, lno, rno)

    # compare other built-in type instance: int, float, ...
    return astdiff_builtin(la, ra, lno, rno)


def pydiff(la, ra):
    global _dc
    _dc = dCache()
    return astdiff(la, ra, None, None)


def usage(writefunc):
    writefunc('Usage:\n%s [--diffdoc] file1 file2\n' % sys.argv[0])
    writefunc('    --diffdoc: add this option if you want to '
              'compare docstrings as well.\n')


if __name__ == '__main__':
    opts, args = getopt(sys.argv[1:], '', ['diffdoc'])
    if len(args) != 2:
        usage(sys.stderr.write)
        exit(1)
    for opt, value in opts:
        if opt == '--diffdoc':
            _diffdoc = True

    lf = args[0]
    rf = args[1]

    la = transformer.parseFile(lf)
    ra = transformer.parseFile(rf)

    r, diffs = pydiff(la, ra)

    if r:
        exit(0)

    print '%d difference(s)' % len(diffs)
    print 'first file: %s\nsecond file: %s\n' % (lf, rf)
    for it in diffs:
        pprint(it)
        print

    exit(1)
