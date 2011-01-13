#!/usr/bin/env python


import pickle
import os, sys, re
import pwd

# cylc suite registration module

class registrations(object):
    def __init__( self, user=None ):
        if not user:
            self.readonly = False
            home = os.environ['HOME']
        elif user == os.environ['USER']:
            self.readonly = False
            home = os.environ['HOME']
        else:
            # attempt to read another user's suite registration
            self.readonly = True
            try:
                home = pwd.getpwnam( user )[5]
            except KeyError, x:
                #raise SystemExit(x)
                raise SystemExit('ERROR, user not found: ' + user )

        # filename used to store suite registrations
        file = os.path.join( home, '.cylc', 'registrations' )
        self.filename = file

        # use a dict to make sure names are unique
        self.registrations = {}

        # make sure the registration directory exists
        if not self.readonly and not os.path.exists( os.path.dirname( file )):
            try:
                os.makedirs( os.path.dirname( file ))
            except Exception,x:
                print "ERROR: unable to create the cylc registration directory"
                print x
                sys.exit(1)

        else:
            self.load_from_file()

    def load_from_file( self ):
        #print "Loading your cylc suite registrations"
        if not os.path.exists( self.filename ):
            # no suites registered yet, so the file does not exist
            return

        input = open( self.filename, 'rb' )
        self.registrations = pickle.load( input )
        input.close()

    def deny_user( self ):
        if self.readonly:
            print "WARNING: you cannot write to another user's registration file"
            return True
        else:
            return False
        
    def dump_to_file( self ):
        if self.deny_user():
            return

        output = open( self.filename, 'w' )
        pickle.dump( self.registrations, output )
        output.close()

    def count( self ):
        return len( self.registrations.keys() )

    def is_registered( self, name ):
        if name in self.registrations.keys():
            return True
        else:
            return False

    def get( self, name ):
        # return suite directory registered under name
        if self.is_registered( name ):
            return self.registrations[ name ]
        else:
            return None

    def get_all( self ):
        return self.registrations.keys()

    def get_list( self ):
        regs = []
        for reg in self.registrations:
            regs.append( (reg, self.registrations[ reg ]))
        return regs

    def unregister( self, name ):
        if self.deny_user():
            return

        if self.is_registered( name ):
            print 'Unregistering ',
            self.print_reg( name )
            del self.registrations[ name ]
        else:
            print 'Name ' + name + ' is not registered'
 
    def register( self, name, dir ):
        if self.deny_user():
            return

        if self.is_registered( name ):
            if dir == self.registrations[ name ]:
                print name + " is already registered:"
                self.print_reg( name )
                return True

            else:
                print "ERROR, " + name + " is already registered:"
                self.print_reg( name )
                return False

        print "New:",
        self.registrations[ name ] = dir
        self.print_reg( name )
        return True

    def print_reg( self, name, pre='', post='' ):
        if name not in self.registrations.keys():
            print "ERROR, name not registered: " + name
            return False
        else:
            print pre + name + ' --> ' + self.registrations[ name ] + post
            return True

    def print_all( self ):
        print 'Number of registrations:', self.count()
        count = 0
        for name in self.registrations.keys():
            count +=1
            self.print_reg( name, pre=' [' + str(count) + '] ' )


if __name__ == '__main__':
    # module test code

    reg = registrations( 'REGISTRATIONS' )

    reg.register( 'foo', 'suites/userguide' )
    reg.register( 'bar', 'suites/userguide' )
    reg.register( 'bar', 'suites/userguidex' )

    reg.print_all()
    reg.dump_to_file()

    print
    reg2 = registrations( 'REGISTRATIONS' )
    reg2.load_from_file()
    reg2.print_all()
