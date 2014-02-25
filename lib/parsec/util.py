#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

"""
Utility functions for printing and manipulating PARSEC NESTED DICTS.
The copy and override functions below assume values are either dicts
(nesting) or shallow collections of simple types.
"""

def listjoin( lst, none_str='' ):
    if not lst:
        # empty list
        return none_str
    else:
        # return string from joined list, but quote all elements if any
        # of them contain comment or list-delimiter characters
        # (currently quoting must be consistent across all elements)
        nlst = []
        quote_me = False
        for item in lst:
            if isinstance( item, str ) and ( '#' in item or ',' in item ):
                quote_me = True
                break
        if quote_me:
            # TODO - this assumes no internal double-quotes
            return ', '.join( [ '"' + str(item) + '"' for item in lst ] )
        else:
            return ', '.join( [ str(item) for item in lst ] )

def printcfg( cfg, level=0, indent=0, prefix='', none_str='' ):
    """
    Recursively pretty-print a parsec config item or section (nested
    dict), as returned by parse.config.get().
    """

    if isinstance(cfg,list):
        # cfg is a single list value
        print prefix + '   '*indent + listjoin( cfg, none_str )
    elif not isinstance(cfg,dict):
        # cfg is a single value
        if not cfg:
            cfg = none_str
        print prefix + '   '*indent +  str(cfg)
    else:
        # cfg is a possibly-nested section
        delayed=[]
        for key,val in cfg.items():
            if isinstance( val, dict ):
                # nested (val is a section)
                # delay output to print top level items before recursing
                delayed.append((key,val))
            else:
                # val is a single value
                if isinstance( val, list ):
                    v = listjoin( val, none_str )
                elif val is None:
                    v = none_str
                else:
                    v = str(val)
                # print "key = val"
                print prefix + '   '*indent + str(key) + ' = ' + v

        for key,val in delayed:
            # print heading
            #if val != None:
            print prefix + '   '*indent + '['*(level+1) + str(key) + ']'*(level+1)
            # recurse into section
            printcfg( val, level=level+1, indent=indent+1, prefix=prefix, none_str=none_str )

def replicate( target, source ):
    """
    Replicate source *into* target. Source elements need not exist in
    target already, so source overrides common elements in target and
    otherwise adds elements to it.
    """
    if not source:
        target = OrderedDict()
        return
    for key,val in source.items():
        if isinstance( val, dict ):
            if key not in target:
                target[key] = OrderedDict()
            replicate( target[key], val )
        elif isinstance( val, list ):
            target[key] = val[:]
        else:
            target[key] = val

def pdeepcopy( source):
    """Make a deep copy of a pdict source"""
    target = OrderedDict()
    replicate( target, source )
    return target

def poverride( target, sparse ):
    """Override items in a target pdict, target sub-dicts must already exist."""
    if not sparse:
        target = OrderedDict()
        return
    for key,val in sparse.items():
        if isinstance( val, dict ):
            poverride( target[key], val )
        elif isinstance( val, list ):
            target[key] = val[:]
        else:
            target[key] = val

def m_override( target, sparse ):
    """Override items in a target pdict. Target keys must already exist
    unless there is a "__MANY__" placeholder in the right position."""
    if not sparse:
        target = OrderedDict()
        return
    for key,val in sparse.items():
        if isinstance( val, dict ):
            if key not in target:
                if '__MANY__' in target:
                    target[key] = OrderedDict()
                    replicate( target[key], target['__MANY__'] )
                else:
                    # TODO - validation prevents this, but handle properly for completeness.
                    raise Exception( "parsec dict override: no __MANY__ placeholder" )
            m_override( target[key], val )
        else:
            if key not in target:
                if '__MANY__' in target:
                    if isinstance( val, list ):
                        target[key] = val[:]
                    else:
                        target[key] = val
                else:
                    # TODO - validation prevents this, but handle properly for completeness.
                    raise Exception( "parsec dict override: no __MANY__ placeholder" )
            if isinstance( val, list ):
                target[key] = val[:]
            else:
                target[key] = val

def un_many( cfig ):
    """Remove any '__MANY__' items from a nested dict, in-place."""
    if not cfig:
        return
    for key,val in cfig.items():
        if key == '__MANY__':
            del cfig[key]
        elif isinstance( val, dict ):
            un_many( cfig[key] )


def itemstr( parents=[], item=None, value=None ):
    """
    Pretty-print an item from list of sections, item name, and value
    E.g.: ([sec1, sec2], item, value) to '[sec1][sec2]item = value'.
    """
    keys = copy(parents)
    if keys and value and not item:
        # last parent is the item
        item = keys[-1]
        keys.remove(item)
    if parents:
        s = '[' + ']['.join(parents) + ']'
    else:
        s = ''
    if item:
        s += str(item)
        if value:
            s += " = " + str(value)
    if not s:
        s = str(value)

    return s


if __name__ == "__main__":
    print 'Item strings:'
    print '  ', itemstr( ['sec1','sec2'], 'item', 'value' )
    print '  ', itemstr( ['sec1','sec2'], 'item' )
    print '  ', itemstr( ['sec1','sec2'] )
    print '  ', itemstr( ['sec1'] )
    print '  ', itemstr( item='item', value='value' )
    print '  ', itemstr( item='item' )
    print '  ', itemstr( value='value' )
    print '  ', itemstr( parents=['sec1','sec2'], value='value' ) # error or useful?

    print 'Configs:'
    printcfg( 'foo', prefix=' > ' )
    printcfg( ['foo','bar'], prefix=' > ' )
    printcfg( {}, prefix=' > ' )
    printcfg( { 'foo' : 1 }, prefix=' > ' )
    printcfg( { 'foo' : None }, prefix=' > ' )
    printcfg( { 'foo' : None }, none_str='(none)', prefix=' > ' )
    printcfg( { 'foo' : { 'bar' : 1 } }, prefix=' > ' )
    printcfg( { 'foo' : { 'bar' : None } }, prefix=' > ' )
    printcfg( { 'foo' : { 'bar' : None } }, none_str='(none)', prefix=' > ' )
    printcfg( { 'foo' : { 'bar' : 1, 'baz' : 2, 'qux' : { 'boo' : None} } }, none_str='(none)', prefix=' > ' )

