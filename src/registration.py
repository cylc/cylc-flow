#!/usr/bin/env python

import pickle
import os, sys, re

# cylc local suite registration

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

class CategoryNotFoundError( RegistrationError ):
    def __init__( self, category, owner=None ):
        self.msg = "ERROR: Category not found " + category
        if owner:
            self.msg += ' (' + owner + ')'

class RegistrationNotValidError( RegistrationError ):
    pass

class registrations(object):
    """
    A simple database of local (user-specific) suite registrations.
    """
    def __init__( self, file=None, centraldb=False ):
        self.centraldb = centraldb
        self.user = os.environ['USER']
        if file:
            # use for testing
            self.file = file
            dir = os.path.dirname( file )
        else:
            # filename used to store suite registrations
            if centraldb:
                dir = os.path.join( os.environ['CYLC_DIR'], 'jdb' )
                self.file = os.path.join( dir, 'registrations' )
            else:
                dir = os.path.join( os.environ['HOME'], '.cylc' )
                self.file = os.path.join( dir, 'registrations' )

        # make sure the registration directory exists
        if not os.path.exists( dir ):
            try:
                os.makedirs( dir )
            except Exception,x:
                print "ERROR: unable to create the cylc registration directory"
                print x
                sys.exit(1)

        self.items = {}  # items[owner][category][name] = (dir,description)
        self.load_from_file()

    def split( self, suite ):
        m = re.match( '^(\w+):(\w+):(\w+)$', suite )
        if m:
            owner, category, name = m.groups()
        else:
            m = re.match( '^(\w+):(\w+)$', suite )
            if m:
                category, name = m.groups()
                owner = self.user
            else:
                if re.match( '^\w+$', suite ):
                    category = 'default'
                    name = suite
                    owner = self.user
                else:
                    raise RegistrationError, 'Illegal suite name: ' + suite
        return ( owner, category, name )

    def load_from_file( self ):
        if not os.path.exists( self.file ):
            # no suites registered yet, so the file does not exist
            return
        input = open( self.file, 'rb' )
        self.items = pickle.load( input )
        input.close()

    def dump_to_file( self ):
        output = open( self.file, 'w' )
        pickle.dump( self.items, output )
        output.close()

    def register( self, suite, dir, description='(no description supplied)' ):
        owner, category, name = self.split( suite )
        if owner != self.user:
            raise RegistrationError, 'You cannot register as another user'
        try:
            regdir, descr = self.items[owner][category][name]
        except KeyError:
            # not registered, do it below.
            pass
        else:
            if regdir == dir:
                # this suite is already registered
                pass
            else:
                # another suite is already registered under this category|name
                raise RegistrationTakenError( suite )
        # register the suite
        if owner not in self.items:
            self.items[owner] = {}
        if category not in self.items[owner]:
            self.items[owner][category] = {}
        self.items[owner][category][name] = (dir, description)

    def unregister_group( self, category ):
        owner = self.user
        try:
            del self.items[owner][category]
        except KeyError:
            raise CategoryNotFoundError( category, owner )

    def unregister( self, suite ):
        owner, category, name = self.split( suite )
        if owner != self.user:
            raise RegistrationError, 'You cannot unregister as another user'
        # check the registration exists:
        dir,descr = self.get( suite )
        # delete it
        del self.items[owner][category][name]
        # delete the category if it is empty
        if len( self.items[owner][category].keys() ) == 0:
            del self.items[owner][category]
        # delete the user slot if it is empty
        if len( self.items[owner].keys() ) == 0:
            del self.items[owner]
 
    def unregister_all( self, silent=False ):
        my_suites = self.get_list( just_suite=True, ownerfilt=[self.user] )
        for suite in my_suites:
            self.print_reg( suite )
            self.unregister( suite )

    def get( self, suite, owner=None ):
        owner, category, name = self.split( suite )
        try:
            reg = self.items[owner][category][name]
        except KeyError:
            raise SuiteNotRegisteredError( suite, owner )
        else:
            return reg

    def get_list( self, just_suite=False, ownerfilt=[], categoryfilt=[] ):
        # return list of [ suite, dir, descr ]
        regs = []
        owners = self.items.keys()
        owners.sort()
        for owner in owners:
            if len(ownerfilt) > 0:
                if owner not in ownerfilt:
                    continue
            categories = self.items[owner].keys()
            categories.sort()
            for category in categories:
                if len(categoryfilt) > 0:
                    if category not in categoryfilt:
                        continue
                names = self.items[owner][category].keys()
                names.sort()
                for name in names:
                    suite = owner + ':' + category + ':' + name
                    dir,descr = self.items[owner][category][name]
                    if just_suite:
                        regs.append( suite )
                    else:
                        regs.append( [suite, dir, descr] )
        return regs

    def clean( self ):
        # delete any invalid registrations owned by you
        categories = self.items[self.user].keys()
        categories.sort()
        for category in categories:
            print 'Group', category + ':'
            names = self.items[self.user][category].keys()
            names.sort()
            for name in names:
                suite = category + ':' + name
                dir,descr = self.items[self.user][category][name] 
                try:
                    self.check_valid( suite )
                except RegistrationNotValidError, x:
                    print ' (DELETING) ' + name + ' --> ' + dir, '(' + str(x) + ')'
                    self.unregister(suite)
                else:
                    print ' (OK) ' + name + ' --> ' + dir

    def check_valid( self, suite ):
        owner, category, name = self.split( suite )
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
        dir,descr = self.get( suite )
        if not verbose:
            print suite + ' --> ' + dir + ' [' + descr + ']'
        else:
            owner, category, name = self.split( suite )
            print '     NAME ' + name + ' --> ' + dir + ' [' + descr + ']'

    def print_all( self, ownerfilt=[], categoryfilt=[], verbose=False ):
        owners = self.items.keys()
        owners.sort()
        for owner in owners:
            if len(ownerfilt) > 0:
                if owner not in ownerfilt:
                    continue
            if verbose:
                print 'OWNER', owner + ':'
            categories = self.items[owner].keys()
            categories.sort()
            for category in categories:
                if len(categoryfilt) > 0:
                    if category not in categoryfilt:
                        continue
                if verbose:
                    print '  GROUP', category + ':'
                names = self.items[owner][category].keys()
                names.sort()
                for name in names:
                    #dir,descr = self.items[owner][category][name] 
                    #print '    ' + name + ' --> ' + dir + ' [' + descr + ']'
                    suite = owner + ':' + category + ':' + name
                    self.print_reg( suite, verbose )

if __name__ == '__main__':
    # unit test
    reg = registrations( 'REGISTRATIONS' )
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

    reg2 = registrations( 'REGISTRATIONS' )
    reg2.load_from_file()
    reg2.print_all()
