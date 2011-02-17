#!/usr/bin/env python

import pickle
import os, sys, re

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
    def __init__( self, suite, owner=None ):
        self.msg = "ERROR: Suite not found " + suite
        if owner:
            self.msg += ' (' + owner + ')'

class groupNotFoundError( RegistrationError ):
    def __init__( self, group, owner=None ):
        self.msg = "ERROR: group not found " + group
        if owner:
            self.msg += ' (' + owner + ')'

class RegistrationNotValidError( RegistrationError ):
    pass

class regsplit( object ):
    def __init__( self, suite ):
        user = os.environ['USER']
        # suite can be:
        # 1/ owner:group:name
        # 2/ group:name (owner is $USER)
        # 3/ name (owner is $USER, group is 'default')
        m = re.match( '^(\w+):(\w+):(\w+)$', suite )
        if m:
            owner, group, name = m.groups()
        else:
            m = re.match( '^(\w+):(\w+)$', suite )
            if m:
                group, name = m.groups()
                owner = user
            else:
                if re.match( '^\w+$', suite ):
                    group = 'default'
                    name = suite
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
     1/ __init__():
       + the database file path
       + and initial call to load_from_file().
    And:
     2/ suite_name():
       + to munge the fully qualified suite name (owner:group:name)
    """

    def load_from_file( self ):
        if not os.path.exists( self.file ):
            # this implies no suites have been registered
            return
        input = open( self.file, 'rb' )
        self.items = pickle.load( input )
        input.close()

    def dump_to_file( self ):
        output = open( self.file, 'w' )
        pickle.dump( self.items, output )
        output.close()

    def register( self, suite, dir, description='(no description supplied)' ):
        owner, group, name = regsplit( suite ).get()
        if owner != self.user:
            raise RegistrationError, 'You cannot register as another user'
        try:
            regdir, descr = self.items[owner][group][name]
        except KeyError:
            # not registered  yet, do it below.
            pass
        else:
            if regdir == dir:
                # OK, this suite is already registered
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

    def unregister( self, suite ):
        owner, group, name = regsplit(suite).get()
        if owner != self.user:
            raise RegistrationError, 'You cannot unregister as another user'
        # check the registration exists:
        dir,descr = self.get( suite )
        # delete it
        del self.items[owner][group][name]
        # delete the group if it is empty
        if len( self.items[owner][group].keys() ) == 0:
            del self.items[owner][group]
        # delete the user slot if it is empty
        if len( self.items[owner].keys() ) == 0:
            del self.items[owner]
 
    def unregister_all( self, silent=False ):
        my_suites = self.get_list( ownerfilt=[self.user] )
        for suite, dir, descr in my_suites:
            self.print_reg( suite )
            self.unregister( suite )

    def unregister_group( self, group ):
        # ToDo: change this to print each unreg as above
        owner = self.user
        try:
            del self.items[owner][group]
        except KeyError:
            raise groupNotFoundError( group, owner )

    def get( self, suite, owner=None ):
        # return suite definition directory
        owner, group, name = regsplit( suite ).get()
        try:
            dir, descr = self.items[owner][group][name]
        except KeyError:
            raise SuiteNotRegisteredError( suite, owner )
        else:
            return ( dir, descr )

    def get_list( self, ownerfilt=[], groupfilt=[] ):
        # return filtered list of tuples:
        # [( suite, dir, descr ), ...]
        regs = []
        owners = self.items.keys()
        owners.sort()
        for owner in owners:
            if len(ownerfilt) > 0:
                if owner not in ownerfilt:
                    continue
            groups = self.items[owner].keys()
            groups.sort()
            for group in groups:
                if len(groupfilt) > 0:
                    if group not in groupfilt:
                        continue
                names = self.items[owner][group].keys()
                names.sort()
                for name in names:
                    suite = owner + ':' + group + ':' + name
                    dir,descr = self.items[owner][group][name]
                    regs.append( (self.suite_name(suite), dir, descr) )
        return regs

    def clean( self ):
        # delete any invalid registrations owned by you
        groups = self.items[self.user].keys()
        groups.sort()
        for group in groups:
            print 'Group', group + ':'
            names = self.items[self.user][group].keys()
            names.sort()
            for name in names:
                suite = group + ':' + name
                dir,descr = self.items[self.user][group][name] 
                try:
                    self.check_valid( suite )
                except RegistrationNotValidError, x:
                    print ' (DELETING) ' + name + ' --> ' + dir, '(' + str(x) + ')'
                    self.unregister(suite)
                else:
                    print ' (OK) ' + name + ' --> ' + dir

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

    def print_reg( self, suite, verbose=False ):
        # check the registration exists:
        suite = regsplit( suite ).get_full()
        dir,descr = self.get( suite )
        if not verbose:
            print self.suite_name( suite ) + ' --> ' + dir + ' [' + descr + ']'
        else:
            owner, group, name = regsplit( suite ).get()
            print '     NAME ' + name + ' --> ' + dir + ' [' + descr + ']'

    def print_all( self, ownerfilt=[], groupfilt=[], verbose=False ):
        owners = self.items.keys()
        owners.sort()
        for owner in owners:
            if len(ownerfilt) > 0:
                if owner not in ownerfilt:
                    continue
            if verbose:
                print 'OWNER', owner + ':'
            groups = self.items[owner].keys()
            groups.sort()
            for group in groups:
                if len(groupfilt) > 0:
                    if group not in groupfilt:
                        continue
                if verbose:
                    print '  GROUP', group + ':'
                names = self.items[owner][group].keys()
                names.sort()
                for name in names:
                    suite = owner + ':' + group + ':' + name
                    self.print_reg( suite, verbose )


class localdb( regdb ):
    """
    Local (user-specific) suite registration database.
    """
    def __init__( self, file=None ):
        self.user = os.environ['USER']
        if file:
            # use for testing
            self.file = file
            dir = os.path.dirname( file )
        else:
            # file in which to store suite registrations
            dir = os.path.join( os.environ['HOME'], '.cylc' )
            self.file = os.path.join( dir, 'registrations' )

        # create initial database directory if necessary
        if not os.path.exists( dir ):
            try:
                os.makedirs( dir )
            except Exception,x:
                print "ERROR: failed to create directory:", dir
                print x
                sys.exit(1)

        self.items = {}  # items[owner][group][name] = (dir,description)
        self.load_from_file()

    def suite_name( self, fullyqualified ):
        # for local use, the user does not need the suite owner prefix
        m = re.match( '^(\w+):(\w+:\w+)$', fullyqualified )
        if m:
            owner, suite = m.groups()
        else:
            raise RegistrationError, 'Illegal fully qualified suite name: ' + fullyqualified
        return suite

    def print_all( self, ownerfilt=[], groupfilt=[], verbose=False ):
        # for local use, don't need to print the owner name
        owners = self.items.keys()
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
            if len(groupfilt) > 0:
                if group not in groupfilt:
                    continue
            if verbose:
                print 'GROUP', group + ':'
            names = self.items[owner][group].keys()
            names.sort()
            for name in names:
                suite = owner + ':' + group + ':' + name
                self.print_reg( suite, verbose )

class centraldb( regdb ):
    """
    Central registration database for sharing suites between users.
    """
    def __init__( self, file=None ):
        self.user = os.environ['USER']
        if file:
            # use for testing
            self.file = file
            dir = os.path.dirname( file )
        else:
            # file in which to store suite registrations
            dir = os.path.join( os.environ['CYLC_DIR'], 'jdb' )
            self.file = os.path.join( dir, 'registrations' )

        # create initial database directory if necessary
        if not os.path.exists( dir ):
            try:
                os.makedirs( dir )
            except Exception,x:
                print "ERROR: failed to create directory:", dir
                print x
                sys.exit(1)

        self.items = {}  # items[owner][group][name] = (dir,description)
        self.load_from_file()

    def suite_name( self, fullyqualified ):
        return fullyqualified

if __name__ == '__main__':
    # unit test
    reg = localdb( os.path.join( os.environ['CYLC_DIR'], 'REGISTRATIONS'))
    reg.unregister_all( silent=True )
    try:
        reg.register( 'foo', 'suites/userguide',      'the quick'    ) # new
        reg.register( 'ONE:bar', 'suites/userguide',  'brown fox'    ) # new
        reg.register( 'TWO:bar', 'suites/userguidex', 'jumped over'  ) # new
        reg.register( 'TWO:baz', 'suites/userguidex' ) # new
        reg.register( 'TWO:baz', 'suites/userguidex' ) # OK repeat
        reg.register( 'TWO:baz', 'suites/userguidexx') # BAD repeat
    except RegistrationError,x:
        print x
    reg.dump_to_file()

    reg2 = localdb( os.path.join( os.environ['CYLC_DIR'], 'REGISTRATIONS'))
    reg2.load_from_file()
    reg2.print_all()
