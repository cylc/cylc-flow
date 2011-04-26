#!/usr/bin/env python

import pickle
import datetime, time
import os, sys, re
from CylcGlobals import central_regdb_dir, local_regdb_dir
# from time import sleep # use to testing locking

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

class RegistrationTakenError( RegistrationError ):
    def __init__( self, suite, owner=None ):
        self.msg = "ERROR: Another suite is registered as " + suite
        if owner:
            self.msg += ' (' + owner + ')'

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

def regjoin( owner, group, name ):
    return owner + ':' + group + ':' + name

class regsplit( object ):
    def __init__( self, suite ):
        user = os.environ['USER']
        # suite can be:
        # 1/ owner:group:name
        # 2/ group:name (owner is $USER)
        m = re.match( '^(\w+):(\w+):(\w+)$', suite )
        if m:
            owner, group, name = m.groups()
        else:
            m = re.match( '^(\w+):(\w+)$', suite )
            if m:
                group, name = m.groups()
                owner = user
            else:
                raise RegistrationError, 'Illegal suite name: ' + suite
        self.owner = owner
        self.group = group
        self.name = name

    def get( self ):
        return self.owner, self.group, self.name
    def get_full( self ):
        return self.owner + ':' + self.group + ':' + self.name
    def get_partial( self ):
        return self.group + ':' + self.name
    def get_name( self ):
        return self.name

class regdb(object):
    """
    A simple suite registration database.
    Derived classes must provide:
     1/ __init__:
       + the database self.dir and self.file (full path)
       + call base class init
    And:
     2/ suiteid():
       + to munge the fully qualified suite name (owner:group:name)
    """
    def __init__( self ):
        self.items = {}  # items[owner][group][name] = (dir,description)
        # create initial database directory if necessary
        if not os.path.exists( self.dir ):
            try:
                os.makedirs( self.dir )
            except Exception,x:
                print "ERROR: failed to create directory:", self.dir
                print x
                sys.exit(1)
        self.user = os.environ['USER']
        self.mtime_at_load = None
        self.lockfile = os.path.join( self.dir, 'lock' )

    def lock( self ):
        if os.path.exists( self.lockfile ):
            print "lock file:", self.lockfile
            raise DatabaseLockedError, 'ERROR: ' + self.file + ' is locked'
        print "Locking database " + self.file
        lockfile = open( self.lockfile, 'wb' )
        lockfile.write( self.user + '\n' )
        lockfile.write( str(datetime.datetime.now()))
        lockfile.close()

    def unlock( self ):
        print "Unlocking database " + self.file
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

    def register( self, suite, dir, description='(no description supplied)', safe=False ):
        # remove trailing '/'
        dir = dir.rstrip( '/' )
        # remove leading './'
        dir = re.sub( '^\.\/', '', dir )
        # also strip / off name in case of registering same name as dir 
        # whilst sitting one level up from the suite dir itself, using
        # tab completion, and getting the args the wrong way around.
        suite = suite.rstrip( '/' )
        # make registered path absolute # see NOTE:ABSPATH above
        if not re.search( '^/', dir ):
            dir = os.path.join( os.environ['PWD'], dir )
        # sleep(20)
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
                raise RegistrationTakenError( suite )

        # register the suite
        if owner not in self.items:
            self.items[owner] = {}
        if group not in self.items[owner]:
            self.items[owner][group] = {}
        self.items[owner][group][name] = (dir, description)
        self.print_reg( suite, prefix='REGISTERED' )

    def reregister( self, suite_from, suite_to, title=None, verbose=False ):
        # LOCKING HANDLED BY CALLERS
        from_owner, from_group, from_name = regsplit(suite_from).get()
        if suite_from == suite_to and title != None:
            safe = True
        else:
            safe = False
        if from_owner != self.user and not safe:
            self.print_reg( suite_from )
            raise RegistrationError, "can't reregister, wrong owner"
        to_owner, to_group, to_name = regsplit(suite_to).get()
        if to_owner != self.user and not safe:
            self.print_reg( suite_to )
            raise RegistrationError, "can't reregister, wrong owner"
        dir, descr = self.get( suite_from )
        self.unregister( suite_from, safe )
        if title:
            self.register( suite_to, dir, title, safe )
        else:
            self.register( suite_to, dir, descr )
        return True

    def reregister_group( self, gfrom, gto, verbose=False, exclusive=False ):
        # move all group members to another (new or existing) group
        # bulk group reregister, owner only
        # LOCKING HANDLED BY CALLERS

        # if input is owner:group, check owner is allowed
        m = re.match( '^(\w+):(\w+)$', gfrom )
        n = re.match( '^(\w+):(\w+)$', gto )
        if m:
            fowner, gfrom = m.groups()
            if fowner != self.user:
                raise RegistrationError, 'You can only reregister your own suites'
        if n:
            towner, gto = n.groups()
            if towner != self.user:
                raise RegistrationError, 'You can only reregister your own suites'
 
        owner = self.user
        if gfrom not in self.items[owner]:
            raise GroupNotFoundError, gfrom
        if gto in self.items[owner] and exclusive:
            raise GroupAlreadyExistsError, gto
        names = self.items[owner][gfrom].keys()
        for name in names:
            dir, descr = self.items[owner][gfrom][name]
            self.register( regjoin(owner,gto,name), dir, descr )
            self.unregister( regjoin(owner,gfrom,name) )
        return True

    def unregister( self, suite, safe=False, verbose=False ):
        # LOCKING HANDLED BY CALLERS
        owner, group, name = regsplit(suite).get()
        if owner != self.user and not safe:
            self.print_reg( suite )
            raise RegistrationError, "can't unregister, wrong owner"
        self.print_reg(suite, prefix='UNREGISTERING', verbose=verbose )
        # delete it
        del self.items[owner][group][name]
        # delete the group if it is empty
        if len( self.items[owner][group].keys() ) == 0:
            del self.items[owner][group]
        # delete the user slot if it is empty
        if len( self.items[owner].keys() ) == 0:
            del self.items[owner]
    
    def unregister_all_fast( self ):
        print 'UNREGISTERING ALL REGISTRATIONS!'
        self.items = {}
 
    def unregister_group_fast( self, group ):
        print 'UNREGISTERING group ', group
        owner = self.user
        try:
            del self.items[owner][group]
        except KeyError:
            raise GroupNotFoundError( group, owner ) 

    def unregister_all( self, verbose=False ):
        my_suites = self.get_list( ownerfilt=self.user )
        for suite, dir, descr in my_suites:
            self.unregister( suite, verbose=verbose )

    def unregister_multi( self, ownerfilt=None, groupfilt=None,
            namefilt=None, verbose=False, invalid=False ):
        changed = False
        owners = self.items.keys()
        owners.sort()
        owner_done = {}
        group_done = {}
        for owner in owners:
            owner_done[owner] = False
            if ownerfilt:
                if not re.match( ownerfilt, owner):
                    continue
            groups = self.items[owner].keys()
            groups.sort()
            for group in groups:
                group_done[group] = False
                if groupfilt:
                    if not re.match( groupfilt, group):
                        continue
                names = self.items[owner][group].keys()
                names.sort()
                for name in names:
                    if namefilt:
                        if not re.match( namefilt, name):
                            continue
                    if verbose:
                        if not owner_done[owner]:
                            print 'OWNER', owner + ':'
                            owner_done[owner] = True
                        if not group_done[group]:
                            print '  GROUP', group + ':'
                            group_done[group] = True
                    suite = owner + ':' + group + ':' + name
                    if invalid:
                        # unregister only if not valid
                        try:
                            self.check_valid( suite )
                        except RegistrationNotValidError, x:
                            print x
                        else:
                            continue
                    self.unregister( suite, verbose )
                    changed = True
        return changed

    def get( self, suite, owner=None ):
        # return suite definition directory and description
        owner, group, name = regsplit( suite ).get()
        try:
            dir, descr = self.items[owner][group][name]
        except KeyError:
            raise SuiteNotRegisteredError( suite )
        else:
            return ( dir, descr )

    def get_list( self, ownerfilt=None, groupfilt=None, namefilt=None, name_only=False ):
        # return filtered list of tuples:
        # [( suite, dir, descr ), ...]
        regs = []
        owners = self.items.keys()
        owners.sort()
        #print ownerfilt
        #print groupfilt
        #print namefilt
        for owner in owners:
            if ownerfilt:
                if not re.match( ownerfilt, owner ):
                    continue
            groups = self.items[owner].keys()
            groups.sort()
            for group in groups:
                if groupfilt:
                    if not re.match( groupfilt, group ):
                        continue
                names = self.items[owner][group].keys()
                names.sort()
                for name in names:
                    if namefilt:
                        if not re.match( namefilt, name ):
                            continue
                    dir,descr = self.items[owner][group][name]
                    if name_only:
                        regs.append( (self.suiteid(owner,group,name)))
                    else:
                        regs.append( (self.suiteid(owner,group,name), dir, descr))
        return regs

    def check_valid( self, suite ):
        owner, group, name = regsplit( suite ).get()
        # raise an exception if the registration is not valid
        dir,descr = self.get( suite )
        if not os.path.isdir( dir ):
            raise RegistrationNotValidError, 'Directory not found: ' + dir
        file = os.path.join( dir, 'suite.rc' )
        if not os.path.isfile( file ): 
            raise RegistrationNotValidError, 'File not found: ' + file
        # OK

    def print_reg( self, suite, prefix='', verbose=False ):
        # check the registration exists:
        suite = regsplit( suite ).get_full()
        owner, group, name = regsplit( suite ).get()
        dir,descr = self.get( suite )
        if not verbose:
            print prefix, self.suiteid( owner,group,name )
            print '    ' + descr 
            print '    ' + dir 
        else:
            print prefix, '     NAME '+ name + ':'
            print '        ' + descr 
            print '        ' + dir 

    def print_multi( self, ownerfilt=None, groupfilt=None, namefilt=None, verbose=False ):
        owners = self.items.keys()
        owners.sort()
        owner_done = {}
        group_done = {}
        count = 0
        for owner in owners:
            owner_done[owner] = False
            if ownerfilt:
                if not re.match( ownerfilt, owner):
                    continue
            groups = self.items[owner].keys()
            groups.sort()
            for group in groups:
                group_done[group] = False
                if groupfilt:
                    if not re.match( groupfilt, group):
                        continue
                names = self.items[owner][group].keys()
                names.sort()
                for name in names:
                    if namefilt:
                        if not re.match( namefilt, name):
                            continue
                    suite = owner + ':' + group + ':' + name
                    if verbose:
                        if not owner_done[owner]:
                            print 'OWNER', owner + ':'
                            owner_done[owner] = True
                        if not group_done[group]:
                            print '  GROUP', group + ':'
                            group_done[group] = True
                    self.print_reg( suite, verbose=verbose )
                    count += 1
        return count

class localdb( regdb ):
    """
    Local (user-specific) suite registration database.
    Internally, registration uses 'owner:group:name' 
    as for the central suite database, but for local
    single-user use, owner is stripped off.
    """
    def __init__( self, file=None ):
        if file:
            # use for testing
            self.file = file
            self.dir = os.path.dirname( file )
        else:
            # file in which to store suite registrations
            self.dir = local_regdb_dir
            self.file = os.path.join( self.dir, 'db' )
        regdb.__init__(self)

    def suiteid( self, owner, group, name ):
        return group + ':' + name

    def print_multi( self, ownerfilt=None, groupfilt=None, namefilt=None, verbose=False ):
        # for local use, don't need to print the owner name
        owners = self.items.keys()
        group_done = {}
        count = 0
        if len(owners) == 0:
            # nothing registered
            return
        if len(owners) > 1:
            # THIS SHOULD NOT HAPPEN
            raise RegistrationError, 'ERROR: multiple owners in local registration db!'
        if owners[0] != self.user:
            # THIS SHOULD NOT HAPPEN
            raise RegistrationError, 'ERROR: wrong suite owner in local registration db!'
        owner = self.user
        # ignoring ownerfilt ... does this matter?
        groups = self.items[owner].keys()
        groups.sort()
        for group in groups:
            group_done[group] = False
            if groupfilt:
                if not re.match( groupfilt, group ):
                    continue
            names = self.items[owner][group].keys()
            names.sort()
            for name in names:
                if namefilt:
                    if not re.match( namefilt, name):
                        continue
                suite = owner + ':' + group + ':' + name
                if verbose:
                    if not group_done[group]:
                        print '  GROUP', group + ':'
                        group_done[group] = True
                self.print_reg( suite, verbose=verbose )
                count += 1
        return count

class centraldb( regdb ):
    """
    Central registration database for sharing suites between users.
    """
    def __init__( self, file=None ):
        if file:
            # use for testing
            self.file = file
            self.dir = os.path.dirname( file )
        else:
            # file in which to store suite registrations
            self.dir = central_regdb_dir
            self.file = os.path.join( self.dir, 'db' )
        regdb.__init__(self)

    def suiteid( self, owner, group, name ):
        return owner + ':' + group + ':' + name

def getdb( suite ):
        type = None
        if re.match( '^(\w+):(\w+):(\w+)$', suite ):
            # owner:group:name
            type = 'central'
        elif re.match( '^(\w+):(\w+)$', suite ): 
            # group:name
            type = 'local'
        elif re.match('^(\w+):(\w+):$', suite ):
            # owner:group:
            type = 'central'
        elif re.match('^(\w+):$', suite ):
            # group:
            type = 'local'
        else:
            raise RegistrationError, 'Illegal registration: ' + suite

        if type == 'central':
            return centraldb()
        else:
            return localdb()
