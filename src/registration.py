#!/usr/bin/python

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

    def count( self ):
        return len( self.registrations.keys() )

    def get( self, name ):
        # return system directory registered under name
        if self.is_registered( name ):
            return self.registrations[ name ]
        else:
            return None

    def is_registered( self, name ):
        if name in self.registrations.keys():
            return True
        else:
            return False

    def unregister_all( self ):
        for name in self.registrations.keys():
            self.unregister( name )

    def unregister( self, name ):
        print 'Unregistering ', 
        self.print_reg( name )
        del self.registrations[ name ]
 
    def register( self, name, dir, force=False ):
        if self.is_registered( name ):
            if dir == self.registrations[ name ]:
                print name + " is already registered:"
                self.print_reg( name )
                return True

            if not force:
                print "ERROR, " + name + " is already registered:"
                self.print_reg( name )
                return False

            print "WARNING, registration override:"
            print "Old:",
            self.print_reg( name )

        if not self.check_dir( dir ):
            return False

        print "New:",
        self.registrations[ name ] = dir
        self.print_reg( name )
        return True

    def load_from_file( self ):
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

    def print_reg( self, name, extra='' ):
        if name not in self.registrations.keys():
            print "ERROR, name not registered: " + name
            return False
        else:
            print ' + ' + name + ' --> ' + self.registrations[ name ] + extra
            return True

    def print_all( self ):
        print self.count(), 'registrations'
        for name in self.registrations.keys():
            self.print_reg( name )

    def check_all( self ):
        print self.count(), 'registrations'
        for name in self.registrations.keys():
            if not self.check_reg( name ):
                self.unregister( name )

    def check_reg( self, name ):
        if self.check_dir( self.registrations[ name ] ):
            self.print_reg( name, ' ... OK' )
            return True
        else:
            self.print_reg( name, ' ... INVALID' )
            return False

    def check_dir( self, dir ):
        if not os.path.exists( dir ):
            print "ERROR, dir not found: " + dir
            return False

        files = [\
                dir + '/system_config.py',
                dir + '/task_classes.py',
                dir + '/task_list.py',
                dir + '/job_submit_methods.py',
                ]

        good = True
        for file in files:
            if not os.path.exists( file ):
                print "ERROR, file not found: " + file
                good = False

        return good
       

if __name__ == '__main__':
    # module test code

    reg = registrations( 'REGISTRATIONS' )

    reg.register( 'userguide', 'systems/userguide' )
    reg.register( 'userguide', 'systems/userguide/waz' )
    reg.register( 'foo', 'systems/userguide' )
    reg.register( 'baz', 'systems/foo' )
    reg.register( 'bar', 'systems/nonexistent' )

    reg.check_all()
    reg.print_all()

    reg.dump_to_file()

    reg2 = registrations( 'REGISTRATIONS' )
    reg2.load_from_file()

    print
    reg2.print_all()
