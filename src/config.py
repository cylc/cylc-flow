#!/usr/bin/env python

# Cylc suite-specific configuration data. The awesome ConfigObj and
# Validate modules do almost everything we need. This just adds a 
# method to check the few things that can't be automatically validated
# according to the spec, $CYLC_DIR/conf/suite-config.spec, such as
# cross-checking some items.

import taskdef
import re, os, sys
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
        
        # check cylc-specific self consistency
        self.__check()

    def __check( self ):
        for task in self['tasks']:

            # check for illegal type modifiers
            for modifier in self['tasks'][task]['type modifier list']:
                if modifier not in self.__class__.allowed_modifiers:
                    raise SuiteConfigError, 'illegal type modifier for ' + task + ': ' + modifier

    def get_task_name_list( self ):
        return self['tasks'].keys()

    def get_task_shortname_list( self ):
        return self['tasks'].keys()

    def generate_task_classes( self, dir ):
        taskdefs = {}
        for label in self['dependency graph']:
            line = self['dependency graph'][label]

            sequence = re.split( '\s*->\s*', line )
            count = 0
            tasks = {}
            for name in sequence:
                if name not in taskdefs:
                    # first time seen; can defined everything except for
                    # possibly other prerequisites.
                    if name not in self['tasks']:
                        raise SuiteConfigError, 'task ' + name + ' not defined'
                    taskconfig = self['tasks'][name]
                    taskd = taskdef.taskdef( name )
                    taskd.type = taskconfig[ 'type' ]
                    taskd.n_restart_outputs['any'] = taskconfig[ 'number of restart outputs' ]
                    taskd.logfiles = []
                    taskd.commands['any'] = taskconfig[ 'command list' ]
                    taskd.hours = taskconfig[ 'valid cycles' ]
                    taskd.type = taskconfig[ 'type' ]
                    taskd.modifiers = taskconfig[ 'type modifier list' ]
                    taskd.outputs['any'] = [ "'" + name + " output 1 ready for ' + self.c_time" ]
                    taskd.environment['any'] = taskconfig[ 'environment' ]
                    taskd.contact_offset['any'] = taskconfig[ 'contact offset hours' ]
                    taskdefs[ name ] = taskd

                if count > 0:
                    taskdefs[name].prerequisites['any'] = [ "'" + prev + " output 1 ready for ' + self.c_time"]
                count += 1
                prev = name

        for name in taskdefs:
            print name, taskdefs[name].type
            taskdefs[ name ].write_task_class( dir )

