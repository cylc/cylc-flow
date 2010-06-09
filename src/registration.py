#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import pickle
import os, sys, re

# cylc system registration module

class registrations:
    
    def __init__( self, file=os.environ['HOME'] + '/.cylc/registrations' ):
        # filename used to store system registrations
        file = os.path.abspath( file )
        self.filename = file

        # use a dict to make sure names are unique
        self.registrations = {}

        # make sure the registration directory exists
        if not os.path.exists( os.path.dirname( file )):
            try:
                os.makedirs( os.path.dirname( file ))
            except Exception,x:
                print "ERROR: unable to create the cylc registration directory"
                print x
                sys.exit(1)

        else:
            self.load_from_file()

    def load_from_file( self ):
        #print "Loading your cylc system registrations"
        if not os.path.exists( self.filename ):
            # no systems registered yet, so the file does not exist
            return

        input = open( self.filename, 'rb' )
        self.registrations = pickle.load( input )
        input.close()
        
    def dump_to_file( self ):
        output = open( self.filename, 'wb' )
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
        # return system directory registered under name
        if self.is_registered( name ):
            return self.registrations[ name ]
        else:
            return None

    def get_all( self ):
        return self.registrations.keys()

    def unregister( self, name ):
        if self.is_registered( name ):
            print 'Unregistering ',
            self.print_reg( name )
            del self.registrations[ name ]
        else:
            print 'Name ' + name + ' is not registered'
 
    def register( self, name, dir ):
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

    reg.register( 'foo', 'systems/userguide' )
    reg.register( 'bar', 'systems/userguide' )
    reg.register( 'bar', 'systems/userguidex' )

    reg.print_all()
    reg.dump_to_file()

    print
    reg2 = registrations( 'REGISTRATIONS' )
    reg2.load_from_file()
    reg2.print_all()
