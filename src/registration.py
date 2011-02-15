#!/usr/bin/env python

import pickle
import os, sys, re
import pwd

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
    def __init__( self, suite ):
        self.msg = "ERROR: Another suite is registered as " + suite

class SuiteNotRegisteredError( RegistrationError ):
    def __init__( self, suite ):
        self.msg = "ERROR: There is no suite registered as " + suite

class RegistrationNotValidError( RegistrationError ):
    pass

class registrations(object):
    """
    A simple database of local (user-specific) suite registrations.
    """
    def __init__( self, file=None ):
        # filename used to store suite registrations
        dir = os.path.join( os.environ['HOME'], '.cylc' )
        # make sure the registration directory exists
        if not os.path.exists( dir ):
            try:
                os.makedirs( dir )
            except Exception,x:
                print "ERROR: unable to create the cylc registration directory"
                print x
                sys.exit(1)

        if file:
            # use for testing
            self.file = file
        else:
            self.file = os.path.join( dir, 'registrations' )

        self.items = {}  # items[category][name] = dir
        self.load_from_file()

    def split( self, suite ):
        m = re.match( '(\w+):(\w+)', suite )
        if m:
            category, name = m.groups()
        elif re.match( '\w+', suite ):
            category = 'default'
            name = suite
        else:
            raise RegistrationError, 'Illegal suite name: ' + suite
        return ( category, name )

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
        category, name = self.split( suite )
        try:
            regdir = self.items[category][name]
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
        if category not in self.items:
            self.items[category] = {}
        self.items[category][name] = (dir, description)

    def unregister( self, suite ):
        category, name = self.split( suite )
        # check the registration exists:
        dir,descr = self.get( suite )
        # delete it
        del self.items[category][name]
        # delete the category if it is empty
        if len( self.items[category] ) == 0:
            del self.items[category]

    def unregister_all( self, silent=False ):
        if not silent:
            self.print_all( prefix='DELETING: ' )
        self.items = {}

    def get( self, suite ):
        category, name = self.split( suite )
        # return suite directory
        try:
            reg = self.items[category][name]
        except KeyError:
            raise SuiteNotRegisteredError( suite )
        else:
            return reg

    def get_list( self ):
        # return list of [ suite, dir, descr ]
        regs = []
        categories = self.items.keys()
        categories.sort()
        for category in categories:
            names = self.items[category].keys()
            names.sort()
            for name in names:
                suite = category + ':' + name
                dir,descr = self.items[category][name]
                regs.append( [suite, dir, descr] )
        return regs

    def clean( self ):
        # delete any invalid registrations
        categories = self.items.keys()
        categories.sort()
        for category in categories:
            print 'Class:', category
            names = self.items[category].keys()
            names.sort()
            for name in names:
                suite = category + ':' + name
                dir,descr = self.items[category][name] 
                try:
                    self.check_valid( suite )
                except RegistrationNotValidError, x:
                    print ' (DELETING) ' + name + ' --> ' + dir, '(' + str(x) + ')'
                    self.unregister(suite)
                else:
                    print ' (OK) ' + name + ' --> ' + dir

    def check_valid( self, suite ):
        category, name = self.split( suite )
        # raise an exception if the registration is not valid
        dir,descr = self.get( suite )
        if not os.path.isdir( dir ):
            raise RegistrationNotValidError, 'Directory not found: ' + dir
        file = os.path.join( dir, 'suite.rc' )
        if not os.path.isfile( file ): 
            raise RegistrationNotValidError, 'File not found: ' + file
        # OK

    def print_all( self, prefix=''):
        categories = self.items.keys()
        categories.sort()
        for category in categories:
            print 'Class:', category
            names = self.items[category].keys()
            names.sort()
            for name in names:
                dir,descr = self.items[category][name] 
                print '  ' + prefix + name + ' --> ' + dir + ' [' + descr + ']'

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
