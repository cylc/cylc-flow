#!/usr/bin/env python

# Cylc suite-specific configuration data. The awesome ConfigObj and
# Validate modules do almost everything we need. This just adds a 
# method to check the few things that can't be automatically validated
# according to the spec, $CYLC_DIR/conf/suite-config.spec, such as
# cross-checking some items.

import taskdef
import re, os, sys, logging
from validate import Validator
from configobj import ConfigObj, get_extra_values

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
    allowed_modifiers = ['contact', 'oneoff', 'sequential', 'catchup', 'catchup_contact']

    def __init__( self, file=None, spec=None ):

        self.taskdefs = {}
        self.loaded = False
        self.coldstart_task_list = []

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
        
        # are there any keywords or sections not present in the spec?
        found_extra = False
        for sections, name in get_extra_values(self):
            # this code gets the extra values themselves
            the_section = self
            for section in sections:
                the_section = self[section]
            # the_value may be a section or a value
            the_value = the_section[name]
            section_or_value = 'value'
            if isinstance(the_value, dict):
                # Sections are subclasses of dict
                section_or_value = 'section'

            section_string = ', '.join(sections) or "top level"
            print 'Extra entry in section: %s. Entry %r is a %s' % (section_string, name, section_or_value)
            found_extra = True

        if found_extra:
            raise SuiteConfigError, "Illegal suite.rc entry found"

        # check cylc-specific self consistency
        self.__check()

    def __check( self ):
        #for task in self['tasks']:
        #    # check for illegal type modifiers
        #    for modifier in self['tasks'][task]['type modifier list']:
        #        if modifier not in self.__class__.allowed_modifiers:
        #            raise SuiteConfigError, 'illegal type modifier for ' + task + ': ' + modifier

        # check families do not define commands, etc.
        pass

    def get_title( self ):
        return self['title']

    def get_description( self ):
        return self['description']

    def get_coldstart_task_list( self ):
        if not self.loaded:
            self.load_taskdefs()
            self.loaded = True
        return self.coldstart_task_list

    def get_task_name_list( self ):
        # return list of task names used in the dependency diagram,
        # not the full tist of defined tasks (self['tasks'].keys())
        if not self.loaded:
            self.load_taskdefs()
            self.loaded = True
        return self.taskdefs.keys()

    def get_task_shortname_list( self ):
        if not self.loaded:
            self.load_taskdefs()
            self.loaded = True
        shorts = []
        for name in self.taskdefs:
            shorts.append( self.taskdefs[ name ].shortname )
        return shorts

    def get_dependent_pairs( self, line ):
        # 'A -> B -> C' ==> [A,B],[B,C]
        # 'A,B -> C'    ==> [A,C],[B,C]
        # 'A,B -> C,D'  ==> [A,C],[A,D],[B,C],[B,D]
        # etc.

        pairs = []
        sequence = re.split( '\s*->\s*', line )

        count = 0
        for item in sequence:
            if count == 0:
                prev = item
                count +=1
                continue

            items = re.split( '\s*', item )
            prevs = re.split( '\s*', prev )

            for i in items:
                for p in prevs:
                    pairs.append( [ p, i ] )

            prev = item
        return pairs

    def load_taskdefs( self ):
        for cycle_list in self['dependency graph']:
            cycles = re.split( '\s*,\s*', cycle_list )

            for label in self['dependency graph'][ cycle_list ]:
                line = self['dependency graph'][cycle_list][label]

                pairs = self.get_dependent_pairs( line )
                   
                tasks = {}

                # NOTE: the following was designed to handle long
                # sequences: A->B->C->D ==> [A,B,C], but has
                # been coopted into handling only pairs, which
                # are the easiest way to handle grouped dependencies:
                # A B -> C D ==> [A,C],[A,D],[B,C],[B,D].
                # It may be possible to simplify the code a bit for pair
                # processing only?
                for pair in pairs:
                    count = 0
                    for name in pair:
                        # check for specific output indicator: TASK(n)
                        specific_output = False
                        m = re.match( '(\w+)\((\d+)\)', name )
                        if m:
                            specific_output = True
                            name = m.groups()[0]
                            output_n = m.groups()[1]
                        # check for model coldstart task indicator, model_coldstart:TASK
                        model_coldstart = False
                        m = re.match( 'model_coldstart:(\w+)', name )
                        if m:
                            model_coldstart = True
                            name = m.groups()[0]

                        # check for coldstart task indicator: coldstart:TASK
                        coldstart = False
                        m = re.match( 'coldstart:(\w+)', name )
                        if m:
                            coldstart = True
                            name = m.groups()[0]

                        # check for oneoff task indicator: oneoff:TASK
                        oneoff = False
                        m = re.match( 'oneoff:(\w+)', name )
                        if m:
                            oneoff = True
                            name = m.groups()[0]

                        if name not in self.taskdefs:
                            # first time seen; define everything except for
                            # possible additional prerequisites.
                            if name not in self['tasks']:
                                raise SuiteConfigError, 'task ' + name + ' not defined'
                            taskconfig = self['tasks'][name]
                            taskd = taskdef.taskdef( name )
                            taskd.description = taskconfig['description']

                            if model_coldstart:
                                self.coldstart_task_list.append( name )
                                taskd.modifiers.append( 'oneoff' )
                                taskd.model_coldstart = True

                            if coldstart:
                                self.coldstart_task_list.append( name )
                                taskd.modifiers.append( 'oneoff' )
                                taskd.coldstart = True

                            if oneoff:
                                taskd.modifiers.append( 'oneoff' )
                                taskd.oneoff = True

                            for item in taskconfig[ 'type list' ]:
                                if item == 'free':
                                    taskd.type = 'free'
                                    continue
                                if item == 'oneoff' or \
                                    item == 'sequential' or \
                                    item == 'catchup':
                                    taskd.modifiers.append( item )
                                    continue
                            
                                m = re.match( 'model\(\s*restarts\s*=\s*(\d+)\s*\)', item )
                                if m:
                                    taskd.type = 'tied'
                                    taskd.n_restart_outputs = int( m.groups()[0] )
                                    continue

                                m = re.match( 'clock\(\s*offset\s*=\s*(\d+)\s*hour\s*\)', item )
                                if m:
                                    taskd.modifiers.append( 'contact' )
                                    taskd.contact_offset = m.groups()[0]
                                    continue

                                m = re.match( 'catchup clock\(\s*offset\s*=\s*(\d+)\s*hour\s*\)', item )
                                if m:
                                    taskd.modifiers.append( 'catchup_contact' )
                                    taskd.contact_offset = m.groups()[0]
                                    continue

                                raise SuiteConfigError, 'illegal task type: ' + item

                            taskd.logfiles = []
                            taskd.commands = taskconfig[ 'command list' ]
                            taskd.environment = taskconfig[ 'environment' ]
                            #taskd.directives = taskconfig[ 'directives' ]
                            #taskd.scripting = taskconfig[ 'scripting' ]

                            self.taskdefs[ name ] = taskd

                        for hour in cycles:
                            hr = int( hour )
                            if hr not in self.taskdefs[name].hours:
                                self.taskdefs[name].hours.append( hr )

                        if count > 0:
                            # MODEL COLDSTART (restart prerequisites)
                            if self.taskdefs[prev_name].model_coldstart:
                                #  prev task must generate my restart outputs at startup 
                                if cycle_list not in self.taskdefs[prev_name].outputs:
                                    self.taskdefs[prev_name].outputs[cycle_list] = []
                                self.taskdefs[prev_name].outputs[ cycle_list ].append( name + " restart files ready for $(CYCLE_TIME)" )

                            # COLDSTART ONEOFF at startup
                            elif self.taskdefs[prev_name].coldstart:
                                #  I can depend on prev task only at startup 
                                if cycle_list not in self.taskdefs[name].coldstart_prerequisites:
                                    self.taskdefs[name].coldstart_prerequisites[cycle_list] = []
                                if prev_specific_output:
                                    # trigger off specific output of previous task
                                    if cycle_list not in self.taskdefs[prev_name].outputs:
                                        self.taskdefs[prev_name].outputs[cycle_list] = []
                                    specout = self['tasks'][prev_name]['outputs'][output_n]
                                    if specout not in self.taskdefs[prev_name].outputs[  cycle_list ]:
                                        self.taskdefs[prev_name].outputs[  cycle_list ].append( specout )
                                    self.taskdefs[name].coldstart_prerequisites[ cycle_list ].append( specout ) 
                                else:
                                    # trigger off previous task finished
                                    self.taskdefs[name].coldstart_prerequisites[ cycle_list ].append( prev_name + "%$(CYCLE_TIME) finished" )
                            # GENERAL
                            else:
                                if cycle_list not in self.taskdefs[name].prerequisites:
                                    self.taskdefs[name].prerequisites[cycle_list] = []
                                if prev_specific_output:
                                    # trigger off specific output of previous task
                                    if cycle_list not in self.taskdefs[prev_name].outputs:
                                        self.taskdefs[prev_name].outputs[cycle_list] = []
                                    specout = self['tasks'][prev_name]['outputs'][output_n]

                                    if specout not in self.taskdefs[prev_name].outputs[  cycle_list ]:
                                        self.taskdefs[prev_name].outputs[  cycle_list ].append( specout )
                                    self.taskdefs[name].prerequisites[ cycle_list ].append( specout )
                                else:
                                    # trigger off previous task finished
                                    self.taskdefs[name].prerequisites[ cycle_list ].append( prev_name + '%$(CYCLE_TIME) finished' )
                        count += 1
                        prev_name = name
                        prev_specific_output = specific_output

        members = []
        my_family = {}
        for name in self['task families']:
            self.taskdefs[name].type="family"
            mems = self['task families'][name]
            self.taskdefs[name].members = mems
            for mem in mems:
                if mem not in members:
                    members.append( mem )
                    taskd = taskdef.taskdef( mem )
                    taskd.member_of = name
                    # take valid hours from the family
                    taskd.hours = self.taskdefs[name].hours
                    taskd.logfiles = []
                    taskconfig = self['tasks'][mem]
                    taskd.commands = taskconfig[ 'command list' ]
                    taskd.environment = taskconfig[ 'environment' ]
                    #taskd.directives = taskconfig[ 'directives'  ]
                    #taskd.scripting = taskconfig[ 'scripting'    ]

                    self.taskdefs[ mem ] = taskd

        # sort hours list for each task
        for name in self.taskdefs:
            self.taskdefs[name].hours.sort( key=int ) 
            #print name, self.taskdefs[name].type, self.taskdefs[name].modifiers

        # define a task insertion group of all coldstart tasks
        self['task insertion groups']['all coldstart tasks'] = self.coldstart_task_list

    def get_task_proxy( self, name, ctime, state, startup ):
        if not self.loaded:
            self.load_taskdefs()
            self.loaded = True
        return self.taskdefs[name].get_task_class()( ctime, state, startup )

    def get_task_class( self, name ):
        if not self.loaded:
            self.load_taskdefs()
            self.loaded = True
        return self.taskdefs[name].get_task_class()

    def get_logging_level( self ):
        # translate logging level strings into logging module parameters
        level = self[ 'logging level' ]
        if level == 'debug':
            value = logging.DEBUG
        elif level == 'info':
            value = logging.INFO
        elif level == 'warning':
            value = logging.WARNING
        elif level == 'error':
            value = logging.ERROR
        elif level == 'critical':
            value = logging.CRITICAL
        return value
