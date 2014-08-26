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

import os, sys, re
from fileparse import parse, FileNotFoundError
from util import printcfg
from validate import validate, check_compulsory, expand, validator
from OrderedDict import OrderedDict
from util import replicate, itemstr
from upgrade import UpgradeError
import cylc.flags

class ParsecError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class ItemNotFoundError( ParsecError ):
    def __init__( self, msg ):
        self.msg = 'ERROR: item not found: ' + msg

class NotSingleItemError( ParsecError ):
    def __init__( self, msg ):
        self.msg = 'ERROR: not a singular item: ' + msg

class config( object ):
    "Object wrapper for parsec functions"

    def __init__( self, spec, upgrader=None, write_proc=False,
            tvars=[], tvars_file=None ):

        self.sparse = OrderedDict()
        self.dense = OrderedDict()
        self.upgrader = upgrader
        self.tvars = tvars
        self.tvars_file = tvars_file
        self.write_proc = write_proc
        self.checkspec( spec )
        self.spec = spec

    def checkspec( self, spec, parents=[] ):
        "check that the file spec is a nested dict of validators"
        for key, value in spec.items():
            pars = parents + [key]
            if isinstance( value, dict ):
                self.checkspec( value, pars )
            else:
                if not isinstance( value, validator ):
                    raise ParsecError( "Illegal file spec item: " + itemstr( pars, repr(value)) )


    def loadcfg( self, rcfile, title="", strict=False, silent=False ):
        """Parse a config file, upgrade or deprecate items if necessary,
        validate it against the spec, and if this is not the first load,
        combine/override with the existing loaded config."""
        try:
            sparse = parse( rcfile, write_proc=self.write_proc,
                template_vars=self.tvars, template_vars_file=self.tvars_file )
        except Exception, x:
            if strict:
                raise
            if not silent or cylc.flags.verbose:
                # no global.rc file, for instance, is not really an error.
                print >> sys.stderr, x
                print >> sys.stderr, "WARNING: " + title + " parsing failed (continuing)"
        else:
            # upgrade deprecated items if necessary
            # (before validation, else validation will fail)
            if self.upgrader is not None:
                try:
                    self.upgrader( sparse, title )
                except UpgradeError, x:
                    print >> sys.stderr, x
                    print >> sys.stderr, "WARNING: " + title + " upgrade error, validation may fail"

            try:
                self.validate( sparse )
            except Exception, x:
                if strict:
                    raise
                if cylc.flags.verbose:
                    print >> sys.stderr, x
                    print >> sys.stderr, "WARNING: " + title + " validation failed"

            else:
                if not self.sparse:
                    self.sparse = sparse
                else:
                    # already loaded, this must be an override
                    replicate( self.sparse, sparse )

    def validate( self, sparse ):
        "Validate sparse config against the file spec."
        validate( sparse, self.spec )
        check_compulsory( sparse, self.spec )

    def expand( self ):
        "Flesh out undefined items with defaults, if any, from the spec."
        if not self.dense:
            self.dense = expand( self.sparse, self.spec )

    def get( self, keys=[], sparse=False ):
        """
        Retrieve items or sections, sparse or dense, by list of keys:
        [sec1,sec2,item] =>
            [sec1]
                [[sec2]]
                    item = value
        """
        if sparse:
            cfg = self.sparse
        else:
            self.expand()
            cfg = self.dense

        parents = []
        for key in keys:
            try:
                cfg = cfg[key]
            except KeyError, x:
                raise ItemNotFoundError( itemstr(parents,key) )
            else:
                parents.append(key)

        return cfg

    def idump( self, items=[], sparse=False, pnative=False, prefix='', oneline=False, none_str='' ):
        """
        items is a list of --item style inputs:
           '[runtime][foo]command scripting'.
        """
        mkeys = []
        null = True
        for i in items:
            null = False
            i = i.lstrip('[')
            i = i.rstrip(']')
            j = re.split( '\]\[*', i )
            mkeys.append(j)
        if null:
            mkeys = [[]]
        self.mdump( mkeys, sparse, pnative, prefix, oneline, none_str )

    def mdump( self, mkeys=[], sparse=False, pnative=False, prefix='', oneline=False, none_str='' ):
        if oneline:
            items = []
            for keys in mkeys:
                item = self.get( keys, sparse )
                if isinstance( item, list ) or isinstance( item, dict ):
                    raise NotSingleItemError( itemstr(keys) )
                if not item:
                    item = none_str or "None"
                items.append(str(item))
            # TODO - quote items if they contain spaces or comment delimiters?
            print prefix + ' '.join( items )
        else:
            for keys in mkeys:
                self.dump( keys, sparse, pnative, prefix, none_str )

    def dump( self, keys=[], sparse=False, pnative=False, prefix='', none_str='' ):
        cfg = self.get( keys, sparse )
        if pnative:
            print cfg
        else:
            printcfg( cfg, prefix=prefix, level=len(keys), none_str=none_str )
