#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
The C3 algorithm is used to linearize multiple inheritance hierarchies
in Python and other languages (MRO = Method Resolution Order). The code
in this doc string is by Samuele Pedroni and Michele Simionato and taken
from the official Python web site, here:
   http://www.python.org/download/releases/2.3/mro/

For cylc, to linearize the runtime inheritance hierarchy, merge()
is unchanged - it works on generic sequences - but mro() had to be
modified to work with lists of names instead of Python base classes.

class __metaclass__(type):
    "All classes are metamagically modified to be nicely printed"
    __repr__ = lambda cls: cls.__name__

class ex_2:
    "Serious order disagreement" #From Guido
    class O: pass
    class X(O): pass
    class Y(O): pass
    class A(X,Y): pass
    class B(Y,X): pass
    try:
        class Z(A,B): pass #creates Z(A,B) in Python 2.2
    except TypeError:
        pass # Z(A,B) cannot be created in Python 2.3

class ex_5:
    "My first example"
    class O: pass
    class F(O): pass
    class E(O): pass
    class D(O): pass
    class C(D,F): pass
    class B(D,E): pass
    class A(B,C): pass

class ex_6:
    "My second example"
    class O: pass
    class F(O): pass
    class E(O): pass
    class D(O): pass
    class C(D,F): pass
    class B(E,D): pass
    class A(B,C): pass

class ex_9:
    "Difference between Python 2.2 MRO and C3" #From Samuele
    class O: pass
    class A(O): pass
    class B(O): pass
    class C(O): pass
    class D(O): pass
    class E(O): pass
    class K1(A,B,C): pass
    class K2(D,B,E): pass
    class K3(D,A): pass
    class Z(K1,K2,K3): pass

def merge(seqs):
    print '\n\nCPL[%s]=%s' % (seqs[0][0],seqs),
    res = []; i=0
    while 1:
      nonemptyseqs=[seq for seq in seqs if seq]
      if not nonemptyseqs: return res
      i+=1; print '\n',i,'round: candidates...',
      for seq in nonemptyseqs: # find merge candidates among seq heads
          cand = seq[0]; print ' ',cand,
          nothead=[s for s in nonemptyseqs if cand in s[1:]]
          if nothead: cand=None #reject candidate
          else: break
      if not cand: raise "Inconsistent hierarchy"
      res.append(cand)
      for seq in nonemptyseqs: # remove cand
          if seq[0] == cand: del seq[0]

def mro(C):
    "Compute the class precedence list (mro) according to C3"
    return merge([[C]]+map(mro,C.__bases__)+[list(C.__bases__)])

def print_mro(C):
    print '\nMRO[%s]=%s' % (C,mro(C))
    print '\nP22 MRO[%s]=%s' % (C,C.mro())

print_mro(ex_9.Z)
"""


from copy import copy


class C3(object):
    def __init__(self, tree=None):
        if not tree:
            tree = {}
        self.tree = tree

    @staticmethod
    def merge(seqs, label=None):
        # print '\n\nCPL[%s]=%s' % (seqs[0][0],seqs),
        res = []
        while True:
            nonemptyseqs = [seq for seq in seqs if seq]
            if not nonemptyseqs:
                return res
            for seq in nonemptyseqs:  # find merge candidates among seq heads
                cand = seq[0]  # print ' ',cand,
                nothead = [s for s in nonemptyseqs if cand in s[1:]]
                if nothead:
                    cand = None  # reject candidate
                else:
                    break
            if not cand:
                prefix = ""
                if label:
                    prefix = "{0}: ".format(label)
                raise Exception(
                    "ERROR: {0}".format(prefix) +
                    "bad runtime namespace inheritance hierarchy.\n" +
                    "See the cylc documentation on multiple inheritance."
                )
            res.append(cand)
            for seq in nonemptyseqs:  # remove cand
                if seq[0] == cand:
                    del seq[0]

    def mro(self, C):
        """Compute the precedence list (mro) according to C3"""
        # copy() required here for tree to remain unchanged
        return self.merge(
            [[C]] + [self.mro(x) for x in self.tree[C]] + [copy(self.tree[C])],
            label=C)


if __name__ == "__main__":
    parents = {}
    parents['root'] = []
    parents['a'] = ['root']
    parents['b'] = ['root']
    parents['foo'] = ['a', 'b']

    print('foo', C3(parents).mro('foo'))

    parents = {}
    parents['o'] = []
    parents['a'] = ['o']
    parents['b'] = ['o']
    parents['c'] = ['o']
    parents['d'] = ['o']
    parents['e'] = ['o']
    parents['k1'] = ['a', 'b', 'c']
    parents['k2'] = ['d', 'b', 'e']
    parents['k3'] = ['d', 'a']
    parents['z'] = ['k1', 'k2', 'k3']

    print('z', C3(parents).mro('z'))

    # Note we can get Python's result by defining an equivalent class
    # hierarchy (with empty class bodies) and printing foo.__mro__.
