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
from fileparse import parse, FileNotFoundError
from validate import validate, expand, override
from upgrade import UpgradeError

"""Some high-level functions for handling parsec config files."""

def load_single( FILE, SPEC, descr, upgrader=None, do_expand=False, verbose=True, strict=False ):
    """
    Parse, upgrade, validate, combine, and expand a single parsec config file.
    If FILE fails to parse or validate just fall back on spec defaults.
    """
    cfg = {}
    try:
        cfg = parse( FILE )
    except FileNotFoundError, x:
        if strict:
            raise
        # not an error - may be relying on defaults
        pass
    except Exception, x:
        if strict:
            raise
        if verbose:
            print >> sys.stderr, x
            print >> sys.stderr, "WARNING: " + descr + " parsing failed (continuing)"
    else:
        # upgrade deprecated items if necessary
        if upgrader is not None:
            if strict:
                raise
            try:
                upgrader( cfg, descr, verbose )
            except UpgradeError, x:
                if verbose:
                    print >> sys.stderr, x
                    print >> sys.stderr, "WARNING: " + descr + " upgrade error, validation may fail"
        # validate
        try:
            validate( cfg, SPEC )
        except Exception, x:
            if strict:
                raise
            if verbose:
                print >> sys.stderr, x
                print >> sys.stderr, "WARNING " + descr + " validation failed (continuing)"
    if do_expand:
        cfg = expand( cfg, SPEC )
    return cfg
 
def load_combined( FILE1, descr1,
                      FILE2, descr2,
                      SPEC, upgrader=None,
                      do_expand=False, verbose=True):
    """
    Parse, upgrade, validate, combine/override, and expand two parsec config files.
    """
    cfg1 = load_single( FILE1, SPEC, descr1, upgrader, False, verbose )
    cfg2 = load_single( FILE2, SPEC, descr2, upgrader, False, verbose )
    if cfg2:
        override( cfg1, cfg2 )
    if do_expand:
        cfg = expand( cfg1, SPEC )
    else:
        cfg = cfg1
    return cfg

