#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os, sys
from copy import copy
from OrderedDict import OrderedDict

"""Utility functions for manipulating parsec nested dicts."""

def printcfg( dct, level=0, indent=0, prefix='', omitNone=False ):
    """
    Recursively print a nested dict in nested INI format.
    """
    delayed=[]
    for key,val in dct.items():
        if isinstance( val, dict ):
            # print top level items before recursing
            delayed.append((key,val))
        elif val != None or not omitNone:
            if isinstance( val, list ):
                v = ', '.join([str(f) for f in val])
            else:
                v = str(val)
            print prefix + '   '*indent + str(key) + ' = ' + v
    for key,val in delayed:
        if val != None:
            print prefix + '   '*indent + '['*(level+1) + str(key) + ']'*(level+1)
        printcfg( val, level=level+1, indent=indent+1, prefix=prefix, omitNone=omitNone)


def replicate( target, source ):
    """Fast deepcopy for a nested dict in which elements may be
    simple types or lists of simple types."""
    for key,val in source.items():
        if isinstance( val, dict ):
            if key not in target:
                if key in ['environment','directives']:
                    target[key] = OrderedDict()
                else:
                    target[key] = {}
            replicate( target[key], val )
        elif isinstance( val, list ):
            target[key] = copy(val)
        else:
            target[key] = val

def override( target, sparse ):
    """Override items in a target dict, all target keys must already exist."""
    for key,val in sparse.items():
        if isinstance( val, dict ):
            override( target[key], val )
        elif isinstance( val, list ):
            target[key] = copy(val)
        else:
            target[key] = val

def m_override( target, sparse ):
    """Override items in a target dict. All target keys must already exist
    unless there is a "__MANY__" key in the right position."""

    for key,val in sparse.items():
        if isinstance( val, dict ):
            if key not in target:
                if '__MANY__' in target:
                    if key in ['environment','directives']:
                        target[key] = tar()
                    else:
                        target[key] = {}
                    replicate( target[key], target['__MANY__'] )
            m_override( target[key], val )
        elif isinstance( val, list ):
            target[key] = copy(val)
        else:
            target[key] = val

def un_many( cfig ):
    """Remove any '__MANY__' items from a nested dict, in-place."""
    for key,val in cfig.items():
        if key == '__MANY__':
            del cfig[key]
        elif isinstance( val, dict ):
            un_many( cfig[key] )

def un_many_replicate( nfig, ofig ):
    """replicate a nested dict, avoiding any '__MANY__' items."""
    for key,val in ofig.items():
        if key == '__MANY__':
            continue
        if isinstance( val, dict ):
            if key not in nfig:
                if key in ['environment','directives']:
                    nfig[key] = OrderedDict()
                else:
                    nfig[key] = {}
            un_many_replicate( nfig[key], ofig[key] )
        elif isinstance( val, list ):
            nfig[key] = copy(val)
        else:
            nfig[key] = val

