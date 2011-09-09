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
        #self.user = os.environ['USER']
        self.mtime_at_load = None
        self.lockfile = os.path.join( self.dir, 'lock' )

    def lock( self ):
        if os.path.exists( self.lockfile ):
            print "lock file:", self.lockfile
            raise DatabaseLockedError, 'ERROR: ' + self.file + ' is locked'
        print "   (locking database " + self.file + ")"
        lockfile = open( self.lockfile, 'wb' )
        #lockfile.write( self.user + '\n' )
        lockfile.write( str(datetime.datetime.now()))
        lockfile.close()

    def unlock( self ):
        print "   (unlocking database " + self.file + ")"
        try:
            os.unlink( self.lockfile )
        except OSError, x:
            print x

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
        self.items = pickle.load( input )
        input.close()

    def dump_to_file( self ):
        output = open( self.file, 'w' )
        pickle.dump( self.items, output )
        output.close()

    def register( self, suite, dir, des='(no description supplied)' ):
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

        self.items[suite] = dir, des

    def get( self, suite ):
        try:
            dir, des = self.items[suite]
        except KeyError:
            raise SuiteNotRegisteredError, "Suite not registered: " + suite
        return dir, des

    def get_list( self, filtr=None ):
        res = []
        for key in self.items:
            if filtr:
                print filtr, key
                if not re.search(filtr, key):
                    continue
            dir, des = self.items[key]
            res.append( [key, dir, des] )
        return res

    def unregister_filtered( self, regex ):
        res = False
        for key in self.items.keys():
            if re.search( regex, key ):
                print 'UNREGISTERING', key 
                del self.items[key]
                res = True
        return res

    def unregister( self, suite ):
        res = False
        for key in self.items.keys():
            if re.match( '^' + suite + r'\b', key):
                print 'UNREGISTERING', key 
                del self.items[key]
                res = True
        return res

    def reregister( self, srce, targ, title=None ):
        res = False
        for key in self.items.keys():
            if key.startswith(srce):
                tmp = self.items[key]
                newkey = re.sub( '^'+srce, targ, key )
                print 'REREGISTERED', key, 'to', newkey
                del self.items[key]
                self.items[newkey] = tmp
                res = True
        return res
         
    def check_valid( self, suite ):
        for key, val in self.items:
            dir, des = val
            if not os.path.isdir( dir ):
                raise RegistrationNotValidError, 'Directory not found: ' + dir
            file = os.path.join( dir, 'suite.rc' )
            if not os.path.isfile( file ): 
                raise RegistrationNotValidError, 'File not found: ' + file

class localdb( regdb ):
    """
    Local (user-specific) suite registration database.
    """
    def __init__( self, file=None ):
        if file:
            # use for testing
            dir = os.path.dirname( file )
        else:
            # file in which to store suite registrations
            dir = local_regdb_dir
            file = os.path.join( dir, 'db' )
        regdb.__init__(self, dir, file)

class centraldb( regdb ):
    """
    Central registration database for sharing suites between users.
    """
    def __init__( self, file=None ):
        if file:
            # use for testing
            dir = os.path.dirname( file )
        else:
            # file in which to store suite registrations
            dir = central_regdb_dir
            file = os.path.join( dir, 'db' )
        regdb.__init__(self, dir, file )

        # ...FORWARD...
        owner, group, name = regsplit( suite ).get()
        if owner != self.user and not safe:
            raise RegistrationError, 'You cannot register as another user'
        try:
            regdir, descr = self.items[owner][group][name]
        except KeyError:
            # not registered  yet, do it below.
            pass
        else:
            if regdir == dir:
                # OK, this suite is already registered
                self.print_reg( suite, prefix='(ALREADY REGISTERED)' )
                return
            else:
                # ERROR, another suite is already using this registration
                raise SuiteTakenError( suite )

if __name__ == '__main__':
    foo = regdb('DB','db')
    foo.register( 'a:d', '/a/d',  'ad' )
    foo.register( 'a:b:d', '/a/b/d', 'abd' )
    foo.register( 'a:b', '/a/b/c', 'abc' )
    print foo.items
    #print foo.get( 'a:b:c' )
    #print foo.get( 'a:d' )
    #foo.unregister( 'a:d' )
    #print foo.items
    #foo.reregister( 'a:b', 'c:twat' )
    #print foo.items
    #print foo.get( 'a:d' )
    #print foo.get( 'a:b:c' )
    #print foo.items

    #try:
    #    print foo.get( 'a:f:c' )
    #except SuiteNotRegisteredError:
    #    print foo.items
    #    sys.exit(1)
    #print foo.get( 'a:x:c' )

