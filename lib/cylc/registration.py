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

import os, sys, re
import pickle
import datetime, time
from regpath import RegPath
from owner import user

# NOTE:ABSPATH (see below)
#   dir = os.path.abspath( dir )
# On GPFS os.path.abspath() returns the full path with fileset
# prefix which can make filenames (for files stored under the 
# cylc suite directory) too long for hardwired limits in the
# UM, which then core dumps. Manual use of $PWD to absolutize a relative
# path, on GPFS, results in a shorter string ... so I use this for now.

# location of the suite registration database:
regdb_path = os.path.join( os.environ['HOME'], '.cylc', 'DB' )

class RegistrationError( Exception ):
    """
    Attributes:
        message - what the problem is. 
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class InvalidFilterError( RegistrationError ):
    def __init__( self, regfilter ):
        self.msg = "ERROR, Invalid filter expression: " + regfilter

class SuiteNotFoundError( RegistrationError ):
    def __init__( self, suite ):
        self.msg = "ERROR, suite not found: " + suite

class SuiteOrGroupNotFoundError( RegistrationError ):
    def __init__( self, sog ):
        self.msg = "ERROR, suite or group not found: " + sog

class SuiteTakenError( RegistrationError ):
    def __init__( self, suite, owner=None ):
        self.msg = "ERROR: " + suite + " is already a registered suite."
        if owner:
            self.msg += ' (' + owner + ')'

class NotAGroupError( RegistrationError ):
    def __init__( self, reg ):
        self.msg = "ERROR: " + reg + " is a registered suite, not a group."

class IsAGroupError( RegistrationError ):
    def __init__( self, reg ):
        self.msg = "ERROR: " + reg + " is already a registered group."

class SuiteNotRegisteredError( RegistrationError ):
    def __init__( self, suite ):
        self.msg = "ERROR: Suite not found " + suite

class GroupNotFoundError( RegistrationError ):
    def __init__( self, group, owner=None ):
        self.msg = "ERROR: group not found " + group
        if owner:
            self.msg += ' (' + owner + ')'

class GroupAlreadyExistsError( RegistrationError ):
    def __init__( self, group, owner=None ):
        self.msg = "ERROR: group already exists " + group
        if owner:
            self.msg += ' (' + owner + ')'

class RegistrationNotValidError( RegistrationError ):
    pass

class DatabaseLockedError( RegistrationError ):
    pass

class DatabaseUnpickleError( RegistrationError ):
    pass

class OwnerError( RegistrationError ):
    pass

class regdb(object):
    """
    A simple suite registration database.
    """
    def __init__( self, dir, file, verbose=False ):
        self.verbose = verbose
        self.dir = dir
        self.file = file
        # items[one][two]...[name] = (dir,title)
        self.items = {}
        # create initial database directory if necessary
        # TODO - CREATE ONLY WHEN REGISTERING?
        if not os.path.exists( self.dir ):
            try:
                os.makedirs( self.dir )
            except Exception,x:
                print >> sys.stderr, "ERROR, failed to create directory:", self.dir
                print >> sys.stderr, x
                sys.exit(1)
        self.mtime_at_load = None
        self.lockfile = self.file + '.lock'
        self.statehash = None

    def get_hash(self):
        return hash( str(sorted(self.items.items())))

    def lock( self ):
        if self.verbose:
            print "locking suite reg db"
        attempts = 0
        while True:
            attempts += 1
            if os.path.exists( self.lockfile ):
                if attempts > 5:
                    print >> sys.stderr, "lock file:", self.lockfile
                    raise DatabaseLockedError, 'ERROR: ' + self.file + ' is locked'
                if self.verbose:
                    print "  (database locked, waiting 1 second, " + str( attempts ) + "/5 attempts)"
                time.sleep(1)
            else:
                break
        # touch file:
        open( self.lockfile, 'w' ).close()
        if self.verbose:
            print "  db locked"

    def unlock( self ):
        if self.verbose:
            print "unlocking suite reg db"
        if os.path.exists( self.lockfile ):
            try:
                os.unlink( self.lockfile )
            except OSError, x:
                if self.verbose:
                    print "  failed to remove lock file: " + self.file
                raise

            else:
                if self.verbose:
                    print "  db unlocked"


    def changed_on_disk( self ):
        # use to detect ONE change in database since we read it,
        # while we have read-only access.
        try:
            st_mtime = os.stat( self.file ).st_mtime 
        except OSError:
            # file not found => no suites registered.
            return False

        if st_mtime != self.mtime_at_load:
            return True
        else:
            return False
        
    def load_from_file( self ):
        if self.verbose:
            print "LOADING DATABASE " + self.file

        # create an empty DB if no suites registered yet
        if not os.path.isfile( self.file ):
            print >> sys.stderr, "WARNING: file not found:", self.file
            print "Creating an empty suite database:", self.file
            self.dump_to_file()

        # get file timestamp
        self.mtime_at_load = os.stat(self.file).st_mtime

        # open the database file
        input = open( self.file, 'rb' )

        try:
            self.items = pickle.load( input )
        except Exception, x:
            input.close()
            print >> sys.stderr, 'failed to unpickle suite database  ' + self.file
            raise DatabaseUnpickleError( 'failed to unpickle suite database  ' + self.file )

        input.close()
        # record state at load
        self.statehash = self.get_hash()

    def dump( self ):
        for i, j in self.items.items():
            print i, j

    def dump_to_file( self ):
        newhash = self.get_hash()
        if newhash != self.statehash:
            if self.verbose:
                print "REWRITING DATABASE"
            output = open( self.file, 'w' )
            pickle.dump( self.items, output )
            output.close()
            self.statehash = newhash
        else:
            if self.verbose:
                print "   (database unchanged)"

    def register( self, suite, dir ):

        suite = RegPath(suite).get()
        for key in self.items:
            if key == suite:
                # there is already a suite of the same name
                raise SuiteTakenError, suite
            elif key.startswith(suite + RegPath.delimiter ):
                # there is already a group of the same name
                raise IsAGroupError, suite
            elif suite.startswith(key + RegPath.delimiter ):
                # suite starts with, to some level, an existing suite name
                raise NotAGroupError, key

        if dir.startswith( '->' ):
            # (alias: dir points to target suite reg)
            # parse the suite for the title
            try:
                title = self.get_suite_title( dir[2:] )
            # parse the suite for the title
            except Exception, x:
                print >> sys.stderr, 'WARNING: an error occurred parsing the suite definition:\n  ', x
                print >> sys.stderr, "Registering the suite with temporary title 'SUITE PARSE ERROR'."
                print >> sys.stderr, "You can update the title later with 'cylc db refresh'.\n"
                title = "SUITE PARSE ERROR"
            # use the lowest level alias
            target = self.unalias( dir[2:] )
            dir = '->' + target
        else:
            # Remove trailing '/'
            dir = dir.rstrip( '/' )
            # Remove leading './'
            dir = re.sub( '^\.\/', '', dir )
            # Make registered path absolute # see NOTE:ABSPATH above
            if not re.search( '^/', dir ):
                dir = os.path.join( os.environ['PWD'], dir )
            # parse the suite for the title
            try:
                title = self.get_suite_title( suite, path=dir )
            except Exception, x:
                print >> sys.stderr, 'WARNING: an error occurred parsing the suite definition:\n  ', x
                print >> sys.stderr, "Registering the suite with temporary title 'SUITE PARSE ERROR'."
                print >> sys.stderr, "You can update the title later with 'cylc db refresh'.\n"
                title = "SUITE PARSE ERROR"

        #if self.verbose:
        print 'REGISTER', suite + ':', dir

        # if title contains newlines we just use the first line here
        title = title.split('\n')[0]
        self.items[suite] = dir, title

    def get( self, reg ):
        suite = self.unalias(reg)
        try:
            dir, title = self.items[suite]
        except KeyError:
            raise SuiteNotRegisteredError, "Suite not registered: " + suite
        return dir, title

    def get_suite( self, reg ):
        suite = self.unalias(reg)
        try:
            dir, title = self.items[suite]
        except KeyError:
            raise SuiteNotRegisteredError, "Suite not registered: " + suite
        return suite, os.path.join( dir, 'suite.rc' )

    def getrc( self, reg ):
        dir, junk = self.get( reg )
        return os.path.join( dir, 'suite.rc' )

    def getdir( self, reg ):
        dir, junk = self.get( reg )
        return dir

    def get_list( self, regfilter=None ):
        # Return a list of all registered suites, or a filtered list.
        # The list can be empty if no suites are registered, or if 
        # the filter rejects all registered suites.
        res = []
        for suite in self.items:
            if regfilter:
                try:
                    if not re.search(regfilter, suite):
                        continue
                except:
                    raise InvalidFilterError, regfilter
            dir, title = self.items[suite]
            res.append( [suite, dir, title] )
        return res

    def unregister( self, exp ):
        dirs = []
        for key in self.items.keys():
            if re.search( exp + '$', key ):
                #if self.verbose:
                dir, junk = self.items[key]
                print 'UNREGISTER', key + ':', dir 
                if dir not in dirs:
                    # (there could be multiple registrations of the same
                    # suite definition).
                    dirs.append(dir)
                del self.items[key]
        # check for aliases that now need to be unregistered
        for key in self.items.keys():
            dir, junk = self.items[key]
            if dir.startswith('->'):
                if re.search( exp, dir[2:] ):
                    #if self.verbose:
                    print 'UNREGISTER (invalidated alias)', key + ':', dir 
                    del self.items[key]
        return dirs

    def reregister( self, srce, targ ):
        srce = RegPath(srce).get()
        targ = RegPath(targ).get()
        for key in self.items:
            if key == targ:
                # There is already a suite of the same name as targ.
                raise SuiteTakenError, targ
            elif key.startswith(targ + RegPath.delimiter):
                # There is already a group of the same name as targ.
                raise IsAGroupError, targ
            elif targ.startswith(key + RegPath.delimiter ):
                # targ starts with, to some level, an existing suite name
                raise NotAGroupError, key
        found = False
        for key in self.items.keys():
            if key.startswith(srce):
                dir, title = self.items[key]
                newkey = re.sub( '^'+srce, targ, key )
                #if self.verbose:
                print 'REREGISTER', key, 'to', newkey
                del self.items[key]
                self.items[newkey] = dir, title
                found = True
        if not found:
            raise SuiteOrGroupNotFoundError, srce

    def alias( self, suite, alias ):
        pseudodir = '->' + suite
        self.register( alias, pseudodir )

    def unalias( self, alias ):
        try:
            dir, title = self.items[alias]
        except KeyError:
            raise SuiteNotFoundError, alias
        if dir.startswith('->'):
            target = self.unalias( dir[2:] )
        else:
            target = alias
        return target

    def get_invalid( self ):
        invalid = []
        for reg in self.items:
            suite = self.unalias(reg)
            dir, junk = self.items[suite]
            rcfile = os.path.join( dir, 'suite.rc' )
            if not os.path.isfile( rcfile ): 
                invalid.append( reg )
        return invalid

    def get_suite_title( self, suite, path=None ):
        "Determine the suite title without a full file parse"
        if path:
            suiterc = os.path.join( path, 'suite.rc' )
        else:
            suite = self.unalias(suite)
            suiterc = self.getrc( suite )

        title = ""
        found_start = False
        done = False
        for xline in open( suiterc, 'rb' ):
            if re.search( '^ *\[', xline ):
                # abort the search: title comes before first [section]
                break
            line = xline.strip()
            if not found_start:
                m = re.match( '^title\s*=\s*([\'\"]+)(.*)', line )
                if m:
                    found_start = True
                    # strip quotes
                    start_quotes, line = m.groups()
            if found_start:
                if line.endswith( start_quotes ):
                    # strip quotes
                    line = re.sub( start_quotes, '', line )
                    done = True
                if title:
                    # adding on a second line on
                    title += " "
                title += line
                if done:
                    break

        if not title:
            title = "No title provided"
        return title

    def refresh_suite_title( self, suite ):
        dir, title = self.items[suite]
        new_title = self.get_suite_title( suite )
        if title == new_title:
            #if self.verbose:
            print 'unchanged:', suite#, '->', title
            changed = False
        else:
            print 'RETITLED:', suite #, '->', new_title
            changed = True
            self.items[suite] = dir, new_title
        return changed

    def get_rcfiles ( self, suite ):
        suite = self.unalias(suite)
        # return a list of all include-files used by this suite
        # TODO - THIS NEEDS TO BE MADE RECURSIVE
        # (only used by cylc_xdot to check if graph has changed).
        rcfiles = []
        try:
            dir, junk = self.items[suite]
        except KeyError:
            raise SuiteNotFoundError, suite
        suiterc = os.path.join( dir, 'suite.rc' )
        rcfiles.append( suiterc )
        for line in open( suiterc, 'rb' ):
            m = re.match( '^\s*%include\s+([\/\w\-\.]+)', line )
            if m:
                rcfiles.append(os.path.join( dir, m.groups()[0]))
        return rcfiles

class localdb( regdb ):
    # TODO - REABSORB THIS BACK INTO THE MAIN regdb CLASS
    # (it dates back to when we had a central db as well).

    """
    Local (user-specific) suite registration database.
    """

    def __init__( self, file=None, verbose=False):
        global regdb_path
        if not file:
            file = regdb_path
        dir = os.path.dirname( file )
        regdb.__init__(self, dir, file, verbose)

