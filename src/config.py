#!/usr/bin/env python

# Cylc suite-specific configuration data. The awesome ConfigObj and
# Validate modules do almost everything we need. This just adds a 
# method to check the few things that can't be automatically validated
# according to the spec, $CYLC_DIR/conf/suite-config.spec, such as
# cross-checking some items.

import os, sys
from validate import Validator
from configobj import ConfigObj

class SuiteConfigError( Exception ):
    """
    Attributes:
        message - what the problem is. 
        TO DO: element - config element causing the problem
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)


class config( ConfigObj ):
    allowed_modifiers = ['dummy', 'contact', 'oneoff', 'sequential', 'catchup', 'catchup_contact']

    def __init__( self, file=None, spec=None ):
        if file:
            self.file = file
        else:
            self.file = os.path.join( os.environ[ 'CYLC_SUITE_DIR' ], 'suite.rc' ),

        if spec:
            self.spec = spec
        else:
            self.spec = os.path.join( os.environ[ 'CYLC_DIR' ], 'conf', 'suite-config.spec')

        # load config
        ConfigObj.__init__( self, self.file, configspec=self.spec )

        # validate and convert to correct types
        val = Validator()
        test = self.validate( val )
        if test != True:
            # TO DO: elucidate which items failed
            # (easy - see ConfigObj and Validate documentation)
            print test
            raise SuiteConfigError, "Suite Config Validation Failed"
        
        self.__check()

    def __check( self ):
        for task in self['tasks']:

            # check for illegal type modifiers
            for modifier in self['tasks'][task]['type modifier list']:
                if modifier not in self.__class__.allowed_modifiers:
                    raise SuiteConfigError, 'illegal type modifier for ' + task + ': ' + modifier

