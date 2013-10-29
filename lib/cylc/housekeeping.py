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

import re, sys, os
import datetime
from cycle_time import ct, CycleTimeError
from batchproc import batchproc

class HousekeepingError( Exception ):
    """
    Attributes:
        message - what the problem is. 
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class NonIdenticalTargetError( HousekeepingError ):
    pass

class OperationFailedError( HousekeepingError ):
    pass

class config_line:
    """
        Process a single cylc housekeeping config line. Matched items
        are batched and members of each batch are processed in parallel
        (in the sense of parallel unix processes). One batch must finish
        before the next is processed.
    """
    legal_ops = [ 'copy', 'move', 'delete' ]
    def __init__( self, source, match, oper, ctime, offset, dest=None, 
            verbose=False, debug=False, mode=None, cheap=False ):
        self.source = source
        self.match = match
        self.ctime = ctime
        try:
            # check the validity of the base cycle time
            ct(ctime)
        except CycleTimeError,x:
            raise HousekeepingError, str(x)
        self.offset = offset
        self.opern = oper 
        self.destn = dest
        self.verbose = verbose
        self.debug = debug
        self.cheap = cheap
        self.mode = mode

        # interpolate SIMPLE environment variables ($foo, ${foo}) into paths
        self.source = os.path.expandvars( self.source )
        if dest:
            self.destn = os.path.expandvars( self.destn )

        # check the validity of the match pattern
        if re.search( '\(\\\d\{10\}\)', self.match ) or \
                re.search( '\(\\\d\{8\}\)', self.match ) and \
                re.search( '\(\\\d\{2\}\)', self.match ):
            pass
        else:
            # putting match in the raise results in it being mangled
            # slightly ( '\d' --> '\\d' ).
            print >> sys.stderr, 'ERROR: ', self.match
            raise HousekeepingError, 'Bad pattern'

        # check the validity of the offset
        try:
            int( self.offset )
        except ValueError:
            raise HousekeepingError, 'Cycle time offset must be integer: ' + self.offset

        # check the validity of the source directory
        if not os.path.isdir( self.source ):
            raise HousekeepingError, 'Source directory not found: ' + self.source
 
        # check the validity of the requested housekeeping operation
        if self.opern not in self.__class__.legal_ops:
            raise HousekeepingError, "Illegal operation: " + self.opern

    def action( self, batchsize ):
        src_entries = 0
        matched = 0
        not_matched = 0
        total = 0
        actioned = 0
        print "________________________________________________________________________"
        print "SOURCE:", self.source
        if self.destn:
            print "TARGET:", self.destn
        print "MATCH :", self.match
        print "ACTION:", self.opern
        foo = ct( self.ctime )
        foo.decrement( hours=self.offset )
        print "CUTOFF:", self.ctime, '-', self.offset, '=', foo.get()
        batch = batchproc( batchsize, verbose=self.verbose )
        for entry in os.listdir( self.source ):
            src_entries += 1
            entrypath = os.path.join( self.source, entry )
            item = hkitem( entrypath, self.match, self.opern, self.ctime, self.offset, 
                    self.destn, self.mode, self.debug, self.cheap )
            if not item.matches():
                not_matched += 1
                continue
            matched += 1
            item.interpolate_destination()
            actioned += batch.add_or_process( item )
        actioned += batch.process()
 
        print 'MATCHED :', str(matched) + '/' + str(src_entries)
        print 'ACTIONED:', str(actioned) + '/' + str(matched)

class config_file:
    """
        Process a cylc housekeeping config file, line by line.
    """
    def __init__( self, file, ctime, only=None, excpt=None, 
            verbose=False, debug=False, mode=None, cheap=False):
        self.lines = []
        if not os.path.isfile( file ):
            raise HousekeepingError, "file not found: " + file 

        print "Parsing housekeeping config file", os.path.abspath( file )
        sys.stdout.flush()

        FILE = open( file, 'r' )
        lines = FILE.readlines()
        FILE.close()

        for line in lines:
            # strip trailing newlines
            line = line.rstrip( '\n' )
            # omit blank lines
            if re.match( '^\s*$', line ):
                continue
            # omit full line comments
            if re.match( '^\s*#', line ):
                continue
            # strip trailing comments
            line = re.sub( '#.*$', '', line )

            # defined environment variables
            m = re.match( '(\w+)=(.*)', line )
            if m:
                varname=m.group(1)
                varvalue=m.group(2)
                os.environ[varname] = os.path.expandvars( varvalue )
                if verbose:
                    print 'Defining variable: ', varname, '=', varvalue
                continue

            # parse line
            tokens = line.split()
            destination = ''
            if len( tokens ) == 5:
                source, match, operation, offset, destination = tokens
            elif len( tokens ) == 4:
                source, match, operation, offset = tokens
            else:
                raise HousekeepingError, "illegal config line:\n  " + line

            skip = False

            if excpt:
                skip = False
                # if line matches any of the given patterns, skip it
                for pattern in re.split( r', *| +', excpt ):
                    if re.search( pattern, line ):
                        skip = True
                        break
            if only:
                skip = True
                # if line does not match any of the given patterns, skip it
                for pattern in re.split( r', *| +', only ):
                    if re.search( pattern, line ):
                        skip = False
                        break
            if skip:
                print "\n   *** SKIPPING " + line
                continue

            self.lines.append( config_line( source, match, operation, 
                ctime, offset, destination, 
                verbose=verbose, debug=debug, mode=mode, cheap=cheap ))

    def action( self, batchsize ):
        for item in self.lines:
            item.action( batchsize )

class hkitem:
    """
        Handle processing of a single source directory entry
    """
    def __init__( self, path, pattern, operation, ctime, offset, destn, mode=None, debug=False, cheap=False ):
        # Assumes the validity of pattern has already been checked
        self.operation = operation
        self.path = path
        self.pattern = pattern
        self.ctime = ctime
        self.offset = offset
        self.destn = destn
        self.matched_ctime = None
        self.debug = debug
        self.cheap = cheap
        self.mode = mode

    def matches( self ):
        if self.debug:
            print "\nSource item:", self.path

        # does path match pattern
        m = re.search( self.pattern, self.path )
        if not m:
            if self.debug:
                print " + does not match"
            return False

        if self.debug:
            print " + MATCH"

        # extract cycle time from path
        mgrps = m.groups()
        if len(mgrps) == 1:
            self.matched_ctime = mgrps[0]
        elif len(mgrps) == 2:
            foo, bar = mgrps
            if len(foo) == 8 and len(bar) == 2:
                self.matched_ctime = foo + bar
            elif len(foo) == 2 and len(bar) == 8:
                self.matched_ctime = bar + foo
            else:
                print "WARNING: Housekeeping match problem:"
                print " + path: "+ self.path
                print " + pattern: " + self.pattern
                print " > extracted time groups:", m.groups()
                return False
        else:
            print "WARNING: Housekeeping match problem:"
            print " + path: "+ self.path
            print " + pattern: " + self.pattern
            print " > extracted time groups:", m.groups()
            return False

        # check validity of extracted cycle time
        try:
            ct(self.matched_ctime)
        except:
            if self.debug:
                print " + extracted cycle time is NOT VALID: " + self.matched_ctime
            return False
        else:
            if self.debug:
                print " + extracted cycle time: " + self.matched_ctime

        # assume ctime is >= self.matched_ctime
        foo = ct( self.ctime )
        bar = ct( self.matched_ctime )
        # gap hours
        gap = foo.subtract_hrs( bar )

        if self.debug:
            print " + computed offset hours", gap,
        if int(gap) < int(self.offset):
            if self.debug:
                print "- ignoring (does not make the cutoff)"
            return False
        
        if self.debug:
            print "- ACTIONABLE (does make the cutoff)"
        return True

    def interpolate_destination( self ):
        # Interpolate cycle time components into destination if necessary.
        if self.destn:
            # destination directory may be cycle time dependent
            dest = self.destn
            dest = re.sub( 'YYYYMMDDHH', self.matched_ctime, dest )
            dest = re.sub( 'YYYYMMDD', self.matched_ctime[0:8], dest )
            dest = re.sub( 'YYYYMM', self.matched_ctime[0:6], dest )
            dest = re.sub( 'MMDD', self.matched_ctime[4:8], dest )
            dest = re.sub( 'YYYY', self.matched_ctime[0:4], dest )
            dest = re.sub( 'MM', self.matched_ctime[4:6], dest )
            dest = re.sub( 'DD', self.matched_ctime[6:8], dest )
            dest = re.sub( 'HH', self.matched_ctime[8:10], dest )
            if self.debug and dest != self.destn:
                print " + expanded destination directory:\n  ", dest
            self.destn = dest

    def execute( self ):
        # construct the command to execute
        command = os.path.join( os.environ['CYLC_DIR'], 'bin', '__hk_' + self.operation ) 
        # ... as a list, for the subprocess module
        comlist = [ command ]

        if self.mode and self.operation != 'delete':
            comlist.append( '--mode=' + self.mode )

        if self.cheap:
            comlist.append( '-c' )

        comlist.append( self.path )

        if self.destn:
            comlist.append( self.destn )

        return comlist
