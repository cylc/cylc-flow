"""
testing overhead of relaxedordereddict
"""

import timeit
import sys

import _ordereddict

class relaxed_ordereddict1(_ordereddict.ordereddict):
    def __init__(self, *args, **kw):
        kw['relax'] = True
        _ordereddict.ordereddict.__init__(self, *args, **kw)

def test0():
    x = _ordereddict.ordereddict()
    x['abcd'] = 0
    x['bcde'] = 1
    x['cdef'] = 2
    x['defg'] = 3
    x['efgh'] = 4
    x['fghi'] = 5
    x['ghij'] = 6
    x['hijk'] = 7
    x['ijkl'] = 8
    x['jklm'] = 9


def test1():
    x = relaxed_ordereddict1()
    x['abcd'] = 0
    x['bcde'] = 1
    x['cdef'] = 2
    x['defg'] = 3
    x['efgh'] = 4
    x['fghi'] = 5
    x['ghij'] = 6
    x['hijk'] = 7
    x['ijkl'] = 8
    x['jklm'] = 9

def test2():
    _ordereddict.relax(True)
    x = relaxed_ordereddict1(abcd=0, bcde= 1, cdef = 2, defg = 3, efgh = 4, fghi = 5, ghij = 6,
             hijk = 7, ijkl = 8,
             jklm = 9)


if __name__ == 'x__main__':
    if len(sys.argv) == 1:
        print test0
        test0()
    elif sys.argv[1] == 1:
        print test1
        test1()
