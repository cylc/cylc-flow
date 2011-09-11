#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
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

import pickle
import datetime, time
import os, sys, re
from conf.CylcGlobals import central_regdb_dir, local_regdb_dir

# NOTE:ABSPATH (see below)
#   dir = os.path.abspath( dir )
# On GPFS os.path.abspath() returns the full path with fileset
# prefix which can make filenames (for files stored under the 
# cylc suite directory) too long for hardwired limits in the
# UM, which then core dumps. Manual use of $PWD to absolutize a relative
# path, on GPFS, results in a shorter string ... so I use this for now.

# local and central suite registration

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
        self.msg = "ERROR: " + reg + " is already a register group."

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

class regdb(object):
    """
    A simple suite registration database.
    """
    def __init__( self, dir, file ):
        self.user = os.environ['USER']
        self.dir = dir
        self.file = file
        # items[one][two]...[name] = (dir,description)
        self.items = {}
        # create initial database directory if necessary
        if not os.path.exists( self.dir ):
            try:
                os.makedirs( self.dir )
            except Exception,x:
                print "ERROR: failed to create directory:", self.dir
                print x
                sys.exit(1)
        self.mtime_at_load = None
        self.lockfile = os.path.join( self.dir, 'lock' )
        self.statehash = None

    def get_hash(self):
        return hash( str(sorted(self.items.items())))

    def lock( self ):
        if os.path.exists( self.lockfile ):
            print "lock file:", self.lockfile
            raise DatabaseLockedError, 'ERROR: ' + self.file + ' is locked'
        print "   (locking database " + self.file + ")"
        lockfile = open( self.lockfile, 'wb' )
        lockfile.write( 'locked by ' + self.user + '\n' )
        lockfile.write( str(datetime.datetime.now()))
        lockfile.close()

    def unlock( self ):
        if os.path.exists( self.lockfile ):
            print "   (unlocking database " + self.file + ")"
            try:
                os.unlink( self.lockfile )
            except OSError, x:
                raise

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
        try:
            self.mtime_at_load = os.stat(self.file).st_mtime
        except OSError:
            # no file: no suites registered  yet
            self.mtime_at_load = time.time()
            return
        input = open( self.file, 'rb' )
        try:
            self.items = pickle.load( input )
        except Exception, x:
            input.close()
            raise RegistrationError, 'ERROR: failed to read database, ' + self.file
        input.close()
        # record state at load
        self.statehash = self.get_hash()

    def dump_to_file( self ):
        newhash = self.get_hash()
        if newhash != self.statehash:
            print "REWRITING DATABASE"
            output = open( self.file, 'w' )
            pickle.dump( self.items, output )
            output.close()
            self.statehash = newhash
        else:
            print "   (database unchanged)"

    def register( self, suite, dir, des='(no description supplied)' ):
        if not dir.startswith( '->' ):  # alias for another reg
            # remove trailing '/'
            dir = dir.rstrip( '/' )
            # remove leading './'
            dir = re.sub( '^\.\/', '', dir )
            # Also strip / off name in case of registering same name as dir 
            # whilst sitting one level up from the suite dir itself, using
            # tab completion, and getting the args the wrong way around.
            suite = suite.rstrip( '/' )
            # make registered path absolute # see NOTE:ABSPATH above

            if not re.search( '^/', dir ):
                dir = os.path.join( os.environ['PWD'], dir )

        for key in self.items.keys():
            if key == suite:
                raise SuiteTakenError, suite
            elif key.startswith(suite + ':'):
                raise IsAGroupError, suite
            elif suite.startswith(key + ':'):
                raise NotAGroupError, key

        print 'REGISTERING', suite, '--->', dir
        self.items[suite] = dir, des

    def get( self, suite ):
        suite, title = self.unalias(suite)
        try:
            dir, des = self.items[suite]
        except KeyError:
            raise SuiteNotRegisteredError, "Suite not registered: " + suite
        return dir, des

    def get_list( self, regfilter=None ):
        # Return a list of all registered suites, or a filtered list.
        # The list can be empty if no suites are registered, or if 
        # the filter rejects all registered suites.
        res = []
        for key in self.items:
            if regfilter:
                try:
                    if not re.search(regfilter, key):
                        continue
                except:
                    raise InvalidFilterError, regfilter
            dir, des = self.items[key]
            res.append( [key, dir, des] )
        return res

    def unregister( self, exp, regfilter=False ):
        if not regfilter:
            # plain suite or group given
            exp = '^' + exp + r'\b'
        dirs = []
        for key in self.items.keys():
            if re.search( exp, key ):
                print 'UNREGISTERING', key 
                dir, junk = self.items[key]
                dirs.append(dir)
                del self.items[key]
        # check for aliases that now need to be unregistered
        for key in self.items.keys():
            dir, junk = self.items[key]
            if dir.startswith('->'):
                if re.search( exp, dir[2:] ):
                    print 'UNREGISTERING invalidated alias', key 
                    del self.items[key]
        return dirs

    def reregister( self, srce, targ, title=None ):
        found = False
        for key in self.items.keys():
            if key.startswith(srce):
                dir, old_title = self.items[key]
                newkey = re.sub( '^'+srce, targ, key )
                print 'REREGISTERED', key, 'to', newkey
                del self.items[key]
                if not title:
                    title = old_title
                self.items[newkey] = dir, title
                found = True
        if not found:
            raise SuiteOrGroupNotFoundError, srce

    def alias( self, suite, alias ):
        suite, title = self.unalias( suite )
        self.register( alias, '->' + suite, title )

    def unalias( self, alias ):
        try:
            dir, title = self.items[alias]
        except KeyError:
            raise SuiteNotFoundError, alias
        if dir.startswith('->'):
            target = dir[2:]
            dir, title = self.items[target]
        else:
            target = alias
        return target, title
         
    def get_invalid( self ):
        invalid = []
        for item in self.items:
            reg, title = self.unalias(item)
            dir, tit = self.items[reg]
            rcfile = os.path.join( dir, 'suite.rc' )
            if not os.path.isfile( rcfile ): 
                invalid.append( item )
        return invalid

class localdb( regdb ):
    """
    Local (user-specific) suite registration database.
    """
    dir = local_regdb_dir
    def __init__( self, file=None ):
        if file:
            # use for testing
            dir = os.path.dirname( file )
        else:
            # file in which to store suite registrations
            dir = self.__class__.dir
            file = os.path.join( dir, 'db' )
        regdb.__init__(self, dir, file)

class centraldb( regdb ):
    """
    Central registration database for sharing suites between users.
    """
    dir = central_regdb_dir
    def __init__( self, file=None ):
        if file:
            # use for testing
            dir = os.path.dirname( file )
        else:
            # file in which to store suite registrations
            dir = self.__class__.dir
            file = os.path.join( dir, 'db' )
        regdb.__init__(self, dir, file )

    def register( self, suite, dir, des='(no description supplied)' ):
        regdb.register( self, self.user + ':' + suite, dir, des )

