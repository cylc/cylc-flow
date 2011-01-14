#!/usr/bin/env python

# Cylc suite-specific configuration data. The awesome ConfigObj and
# Validate modules do almost everything we need. This just adds a 
# method to check the few things that can't be automatically validated
# according to the spec, $CYLC_DIR/conf/suiterc.spec, such as
# cross-checking some items.

import taskdef
import re, os, sys, logging
from validate import Validator
from configobj import get_extra_values
from cylcconfigobj import CylcConfigObj
from registration import registrations

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

class DepGNode:
    def __init__( self, item ):
        # [TYPE:]NAME[(T+/-OFFSET)][:OUTPUT]
        # where [] => optional:

        # TYPE:
        self.coldstart = False
        self.model_coldstart = False
        self.oneoff = False

        # INTERCYCLE DEP
        self.intercycle = False
        self.sign = None    # '+' or '-'
        self.offset = None  

        # SPECIFIC OUTPUT
        self.output = None

        self.name = item

        # INTERCYCLE
        m = re.match( '(.*)\(\s*T\s*([+-])\s*(\d+)\s*\)(.*)', self.name )
        if m:
            self.intercycle = True
            pre, self.sign, self.offset, post = m.groups()
            self.name = pre + post
            if self.sign == '+':
                raise SuiteConfigError, item + ": only negative offsets allowed in dependency graph (e.g. T-6)"

        # TYPE
        m = re.match( '^model_coldstart:(\w+)', self.name )
        if m:
            self.model_coldstart = True
            self.name = m.groups()[0]

        m = re.match( '^coldstart:(\w+)', self.name )
        if m:
            self.coldstart = True
            self.name = m.groups()[0]

        m = re.match( '^oneoff:(\w+)', self.name )
        if m:
            self.oneoff = True
            self.name = m.groups()[0]

        # OUTPUT
        m = re.match( '(\w+):(\w+)', self.name )
        if m:
            self.name, self.output = m.groups()

class config( CylcConfigObj ):
    allowed_modifiers = ['contact', 'oneoff', 'sequential', 'catchup', 'catchup_contact']

    def __init__( self, suite=None ):
        self.taskdefs = {}
        self.loaded = False
        self.coldstart_task_list = []

        if suite:
            reg = registrations()
            if reg.is_registered( suite ):
                self.dir = reg.get( suite )
            else:
                reg.print_all()
                raise SuiteConfigError, "Suite " + suite + " is not registered"

            self.file = os.path.join( self.dir, 'suite.rc' )
        else:
            self.file = os.path.join( os.environ[ 'CYLC_SUITE_DIR' ], 'suite.rc' ),

        self.spec = os.path.join( os.environ[ 'CYLC_DIR' ], 'conf', 'suiterc.spec')

        # load config
        CylcConfigObj.__init__( self, self.file, configspec=self.spec )

        # validate and convert to correct types
        val = Validator()
        test = self.validate( val )
        if test != True:
            # TO DO: elucidate which items failed
            # (easy - see ConfigObj and Validate documentation)
            print test
            raise SuiteConfigError, "Suite Config Validation Failed"
        
        # TO DO: THE FOLLOWING CODE FAILS PRIOR TO RAISING THE
        # EXCEPTION; EXPERIMENT WITH ERRONEOUS CONFIG ENTRIES.
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

        # make logging and state directories relative to $HOME
        # unless they are specified as absolute paths
        home = os.environ['HOME']
        logdir = self['top level logging directory']
        if not re.match( '^/', logdir ):
           self['top level logging directory'] = os.path.join( home, logdir )
        statedir = self['top level state dump directory']
        if not re.match( '^/', statedir ):
           self['top level state dump directory'] = os.path.join( home, statedir )

    def get_filename( self ):
        return self.file
    def get_dirname( self ):
        return self.dir

    def prerequisite_decrement( self, msg, offset ):
        return re.sub( "\$\(CYCLE_TIME\)", "$(CYCLE_TIME - " + offset + ")", msg )

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
        #print self['taskdefs']

        for name in self['taskdefs']:
            taskd = taskdef.taskdef( name )
            taskd.load_oldstyle( name, self['taskdefs'][name], self['ignore task owners'] )
            self.taskdefs[name] = taskd

        for cycle_list in self['dependency graph']:

            for label in self['dependency graph'][ cycle_list ]:
                line = self['dependency graph'][cycle_list][label]

                pairs = self.get_dependent_pairs( line )
                   
                tasks = {}

                # NOTE: the following code was designed to handle long
                # sequences: A->B->C->D ==> [A,B,C], but now we
                # process only pairs, which is the easiest way to handle
                # grouped dependencies: 
                # A B -> C D ==> [A,C],[A,D],[B,C],[B,D].
                # It may be possible to simplify a bit for pairs only?

                for pair in pairs:
                    first_of_pair = True
                    for item in pair:
                        dgtask = DepGNode( item )
                        name = dgtask.name
                        model_coldstart = dgtask.model_coldstart
                        coldstart = dgtask.coldstart
                        oneoff = dgtask.oneoff
                        output = dgtask.output
                        intercycle = dgtask.intercycle
                        sign = dgtask.sign
                        offset = dgtask.offset

                        if name not in self['tasks']:
                            raise SuiteConfigError, 'task ' + name + ' not defined'

                        if name not in self.taskdefs:
                            self.taskdefs[ name ] = self.get_taskdef( name, model_coldstart, coldstart, oneoff )
                        
                        self.taskdefs[ name ].add_hours( cycle_list )

                        if first_of_pair:
                            first_of_pair = False
                            prev_name = name
                            prev_output = output
                            prev_intercycle = intercycle
                            if intercycle:
                                prev_sign = sign
                                prev_offset = offset
                        else:
                            # MODEL COLDSTART (restart prerequisites)
                            if self.taskdefs[prev_name].model_coldstart:
                                #  prev task must generate my restart outputs at startup 
                                if cycle_list not in self.taskdefs[prev_name].outputs:
                                    self.taskdefs[prev_name].outputs[cycle_list] = []
                                self.taskdefs[prev_name].outputs[cycle_list].append( name + " restart files ready for $(CYCLE_TIME)" )

                            # COLDSTART ONEOFF at startup
                            elif self.taskdefs[prev_name].coldstart:
                                #  I can depend on prev task only at startup 
                                if cycle_list not in self.taskdefs[name].coldstart_prerequisites:
                                    self.taskdefs[name].coldstart_prerequisites[cycle_list] = []
                                if prev_output:
                                    # trigger off specific output of previous task
                                    if cycle_list not in self.taskdefs[prev_name].outputs:
                                        self.taskdefs[prev_name].outputs[cycle_list] = []
                                    msg = self['tasks'][prev_name]['outputs'][prev_output]
                                    if msg not in self.taskdefs[prev_name].outputs[  cycle_list ]:
                                        self.taskdefs[prev_name].outputs[  cycle_list ].append( msg )
                                    self.taskdefs[name].coldstart_prerequisites[ cycle_list ].append( msg ) 
                                else:
                                    # trigger off previous task finished
                                    self.taskdefs[name].coldstart_prerequisites[ cycle_list ].append( prev_name + "%$(CYCLE_TIME) finished" )
                            else:
                                # GENERAL
                                if cycle_list not in self.taskdefs[name].prerequisites:
                                    self.taskdefs[name].prerequisites[cycle_list] = []
                                if prev_output:
                                    # trigger off specific output of previous task
                                    if cycle_list not in self.taskdefs[prev_name].outputs:
                                        self.taskdefs[prev_name].outputs[cycle_list] = []
                                    msg = self['tasks'][prev_name]['outputs'][prev_output]
                                    if msg not in self.taskdefs[prev_name].outputs[ cycle_list ]:
                                        self.taskdefs[prev_name].outputs[ cycle_list ].append( msg )
                                    if prev_intercycle:
                                        msg = self.prerequisite_decrement( msg, prev_offset )
                                    self.taskdefs[name].prerequisites[ cycle_list ].append( msg )
                                else:
                                    # trigger off previous task finished
                                    msg = prev_name + "%$(CYCLE_TIME) finished" 
                                    if prev_intercycle:
                                        msg = self.prerequisite_decrement( msg, prev_offset )
                                    self.taskdefs[name].prerequisites[ cycle_list ].append( msg )

        members = []
        my_family = {}
        for name in self['task families']:
            self.taskdefs[name].type="family"
            mems = self['task families'][name]
            self.taskdefs[name].members = mems
            for mem in mems:
                if mem not in members:
                    members.append( mem )
                    # TO DO: ALLOW MORE GENERAL INTERNAL FAMILY MEMBERS?
                if mem not in self.taskdefs:
                    self.taskdefs[ mem ] = self.get_taskdef( mem )
                self.taskdefs[mem].member_of = name
                # take valid hours from the family
                # (REPLACES HOURS if member appears in graph section)
                self.taskdefs[mem].hours = self.taskdefs[name].hours

        # sort hours list for each task
        for name in self.taskdefs:
            self.taskdefs[name].hours.sort( key=int ) 
            #print name, self.taskdefs[name].type, self.taskdefs[name].modifiers

        # define a task insertion group of all coldstart tasks
        self['task insertion groups']['all coldstart tasks'] = self.coldstart_task_list

    def get_taskdef( self, name, model_coldstart=False, coldstart=False, oneoff=False ):
        if name not in self['tasks']:
            raise SuiteConfigError, 'task ' + name + ' not defined'
        taskconfig = self['tasks'][name]
        taskd = taskdef.taskdef( name )
        taskd.description = taskconfig['description']
        if not self['ignore task owners']:
            taskd.owner = taskconfig['owner']
        taskd.execution_timeout_minutes = taskconfig['execution timeout minutes']
        taskd.reset_execution_timeout_on_incoming_messages = taskconfig['reset execution timeout on incoming messages']
        if taskconfig['job submission method'] != None:
            taskd.job_submit_method = taskconfig['job submission method']
        else:
            taskd.job_submit_method = self['job submission method']

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

        taskd.type = taskconfig[ 'type' ]

        for item in taskconfig[ 'type modifier list' ]:
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

        taskd.logfiles = taskconfig[ 'log file list' ]
        taskd.commands = taskconfig[ 'command list' ]
        taskd.environment = taskconfig[ 'environment' ]
        taskd.directives = taskconfig[ 'directives' ]
        taskd.scripting = taskconfig[ 'scripting' ]

        return taskd

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



