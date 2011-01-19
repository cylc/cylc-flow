#!/usr/bin/env python

# Cylc suite-specific configuration data. The awesome ConfigObj and
# Validate modules do almost everything we need. This just adds a 
# method to check the few things that can't be automatically validated
# according to the spec, $CYLC_DIR/conf/suiterc.spec, such as
# cross-checking some items.

import taskdef
import pygraphviz
import re, os, sys, logging
from mkdir_p import mkdir_p
from validate import Validator
from configobj import get_extra_values
from cylcconfigobj import CylcConfigObj
from registration import registrations

class dependency:
    def __init__( self, left, right, type ):
        self.left = left
        self.right = right
        self.type = type

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
        m = re.match( '^(\w+)\|', self.name )
        if m:
            self.oneoff = True
            self.name = m.groups()[0]

        # OUTPUT
        m = re.match( '(\w+):(\w+)', self.name )
        if m:
            self.name, self.output = m.groups()

class config( CylcConfigObj ):
    allowed_modifiers = ['contact', 'oneoff', 'sequential', 'catchup', 'catchup_contact']

    def __init__( self, suite=None, dummy_mode=False ):
        self.dummy_mode = dummy_mode
        self.taskdefs = {}
        self.loaded = False
        self.task_graph_labels = {}

        if suite:
            self.suite = suite
            reg = registrations()
            if reg.is_registered( suite ):
                self.dir = reg.get( suite )
            else:
                reg.print_all()
                raise SuiteConfigError, "Suite " + suite + " is not registered"

            self.file = os.path.join( self.dir, 'suite.rc' )
        else:
            self.suite = os.environ[ 'CYLC_SUITE_NAME' ]
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

        # allow $CYLC_SUITE_NAME in job submission log directory
        jsld = self['job submission log directory' ] 
        jsld = re.sub( '\${CYLC_SUITE_NAME}', self.suite, jsld )
        jsld = re.sub( '\$CYLC_SUITE_NAME', self.suite, jsld )

        # make logging and state directories relative to $HOME
        # unless they are specified as absolute paths
        self['top level logging directory'] = self.make_dir_absolute( self['top level logging directory'] )
        self['top level state dump directory'] = self.make_dir_absolute( self['top level state dump directory'] )
        self['job submission log directory' ] = self.make_dir_absolute( jsld )

    def make_dir_absolute( self, indir ):
        # make dir relative to $HOME unless already absolute
        home = os.environ['HOME']
        if not re.match( '^/', indir ):
            outdir = os.path.join( home, indir )
        else:
            outdir = indir
        return outdir

    def create_directories( self ):
        # create logging, state, and job log directories if necessary
        for dir in [
            self['top level logging directory'], 
            self['top level state dump directory'],
            self['job submission log directory'] ]: 
            mkdir_p( dir )

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
        # TO DO: automatically determine this by parsing the dependency
        #        graph - requires some thought.
        ##if not self.loaded:
        ##    self.load_taskdefs()
        ##return self.coldstart_task_list

        # For now user must define this:
        return self['coldstart task list']

    def get_task_name_list( self ):
        # return list of task names used in the dependency diagram,
        # not the full tist of defined tasks (self['tasks'].keys())
        if not self.loaded:
            self.load_taskdefs()
        return self.taskdefs.keys()

    def update_task_graph_labels( self, label, line ):
        seen = []
        for item in re.split( '\s*=[mc=]=>\s*', line ):
            for task in re.split( '\s*&\s*', item ):
                foo = re.sub( '\|$', '', task )
                bar = re.sub( '\(\s*T.*\)', '', foo )
                baz = re.sub( ':\w+$', '', bar )
                seen.append( baz )
        #print label, '::', line, '::', seen
        #for task in seen:
        #    self.task_graph_labels[ task ] = label
        self.task_graph_labels[label] = seen

    def get_task_labels( self ):
        return self.task_graph_labels

    def get_dependent_pairs( self, line ):
        # 'A ===> B ===> C' : [A ===> B],[B ===> C]
        # 'A,B ===> C'      : [A ===> C],[B ===> C]
        # 'A,B ===> C,D'    : [A ===> C],[A ===> D],[B ===> C],[B ===> D]
        # etc.

        pairs = []
        # split on arrows, detecting type of dependency arrow
        # ( ===>, =c=>, =m=> )
        sequence = re.split( '\s*=([mc=])=>\s*', line )

        for i in range( 0, len(sequence)-1, 2 ):
            left = sequence[i]
            op = sequence[i+1]
            right = sequence[i+2]

            if op == '=':
                type = 'normal'
            elif op == 'c':
                type = 'coldstart'
            elif op == 'm':
                type = 'model coldstart'
            else:
                raise SuiteConfigError, 'Unknown dependency arrow: ' + '=' + op + '=>' 

            rights = re.split( '\s*&\s*', right )
            lefts = re.split( '\s*&\s*', left )

            for r in rights:
                for l in lefts:
                    pairs.append( dependency( DepGNode(l), DepGNode(r), type ))

        return pairs

    def process_dep_pair( self, pair, cycle_list ):
        left = pair.left
        right = pair.right
        type = pair.type

        for node in [left, right]:
            if node.name not in self['tasks']:
                #raise SuiteConfigError, 'task ' + node.name + ' not defined'
                # ALLOW DUMMY TASKS TO BE DEFINED BY GRAPH ONLY
                # TO DO: CHECK SENSIBLE DEFAULTS ARE DEFINED FOR ALL
                # TASKDEF PARAMETERS.
                self.taskdefs[ node.name ] = taskdef.taskdef(node.name)

            if node.name not in self.taskdefs:
                self.taskdefs[ node.name ] = self.get_taskdef( node.name, type, node.oneoff )
                        
            self.taskdefs[ node.name ].add_hours( cycle_list )

        if pair.type == 'model coldstart':
            # MODEL COLDSTART (restart prerequisites)
            #  prev task must generate my restart outputs at startup 
            if cycle_list not in self.taskdefs[left.name].outputs:
                self.taskdefs[left.name].outputs[cycle_list] = []
            self.taskdefs[left.name].outputs[cycle_list].append( right.name + " restart files ready for $(CYCLE_TIME)" )

        elif pair.type == 'coldstart':
            # COLDSTART ONEOFF at startup
            #  I can depend on prev task only at startup 
            if cycle_list not in self.taskdefs[right.name].coldstart_prerequisites:
                self.taskdefs[right.name].coldstart_prerequisites[cycle_list] = []
            if left.output:
                # trigger off specific output of previous task
                if cycle_list not in self.taskdefs[left.name].outputs:
                    self.taskdefs[left.name].outputs[cycle_list] = []
                msg = self['tasks'][left.name]['outputs'][left.output]
                if msg not in self.taskdefs[left.name].outputs[  cycle_list ]:
                    self.taskdefs[left.name].outputs[  cycle_list ].append( msg )
                self.taskdefs[right.name].coldstart_prerequisites[ cycle_list ].append( msg ) 
            else:
                # trigger off previous task finished
                self.taskdefs[right.name].coldstart_prerequisites[ cycle_list ].append( left.name + "%$(CYCLE_TIME) finished" )
        else:
            # GENERAL
            if cycle_list not in self.taskdefs[right.name].prerequisites:
                self.taskdefs[right.name].prerequisites[cycle_list] = []
            if left.output:
                # trigger off specific output of previous task
                if cycle_list not in self.taskdefs[left.name].outputs:
                    self.taskdefs[left.name].outputs[cycle_list] = []
                msg = self['tasks'][left.name]['outputs'][left.output]
                if msg not in self.taskdefs[left.name].outputs[ cycle_list ]:
                    self.taskdefs[left.name].outputs[ cycle_list ].append( msg )
                if left.intercycle:
                    self.taskdefs[left.name].intercycle = True
                    msg = self.prerequisite_decrement( msg, left.offset )
                self.taskdefs[right.name].prerequisites[ cycle_list ].append( msg )
            else:
                # trigger off previous task finished
                msg = left.name + "%$(CYCLE_TIME) finished" 
                if left.intercycle:
                    self.taskdefs[left.name].intercycle = True
                    msg = self.prerequisite_decrement( msg, left.offset )
                self.taskdefs[right.name].prerequisites[ cycle_list ].append( msg )

    def get_coldstart_graphs( self ):
        if not self.loaded:
            self.load_taskdefs()
        graphs = {}
        for cycle_list in self['dependency graph']:
            for label in self['dependency graph'][ cycle_list ]:
                line = self['dependency graph'][cycle_list][label]
                pairs = self.get_dependent_pairs( line )
                for pair in pairs:
                    for cycle in re.split( '\s*,\s*', cycle_list ):
                        if cycle not in graphs:
                            graphs[cycle] = pygraphviz.AGraph(directed=True)
                        left = pair.left.name + '(' + cycle + ')'
                        right = pair.right.name + '(' + cycle + ')'
                        graphs[cycle].add_edge( left, right )
        return graphs 

    def get_full_graph( self ):
        if not self.loaded:
            self.load_taskdefs()
        edges = {}
        for cycle_list in self['dependency graph']:
            for label in self['dependency graph'][ cycle_list ]:
                line = self['dependency graph'][cycle_list][label]
                pairs = self.get_dependent_pairs( line )
                for cycle in re.split( '\s*,\s*', cycle_list ):
                    print cycle, line
                    if int(cycle) not in edges:
                        edges[ int(cycle) ] = []
                    for pair in pairs:
                        if pair not in edges[int(cycle)]:
                            edges[ int(cycle) ].append( pair )

        graph = pygraphviz.AGraph(directed=True)
        cycles = edges.keys()
        cycles.sort()
        # note: need list rotation in order to coldstart start at
        # another cycle time.
        oneoff_done = {}
        coldstart_done = False
        for cycle in cycles:
            for pair in edges[cycle]:
                lname = pair.left.name
                rname = pair.right.name
                type  = pair.type
                if 'oneoff' in self.taskdefs[ lname ].modifiers:
                    if lname in oneoff_done:
                        if oneoff_done[lname] != cycle:
                            continue
                    else:
                        oneoff_done[lname] = cycle

                if coldstart_done and self.taskdefs[ lname ].type == 'tied':
                    # TO DO: need task-specific prev cycle:
                    prev = self.prev_cycle( cycle, cycles )
                    a = lname + '(' + str(prev) + ')'
                    b = lname + '(' + str(cycle) + ')'
                    graph.add_edge( a, b )

                left = lname + '(' + str(cycle) + ')'
                right = rname + '(' + str(cycle) + ')'
                graph.add_edge( left, right )
            coldstart_done = True
        return graph

    def prev_cycle( self, cycle, cycles ):
        i = cycles.index( cycle )
        if i == 0:
            prev = cycles[-1]
        else:
            prev = cycles[i-1]
        return prev

    def load_taskdefs( self ):
        for name in self['taskdefs']:
            taskd = taskdef.taskdef( name )
            taskd.load_oldstyle( name, self['taskdefs'][name], self['ignore task owners'] )
            self.taskdefs[name] = taskd

        for cycle_list in self['dependency graph']:
            for label in self['dependency graph'][ cycle_list ]:
                line = self['dependency graph'][cycle_list][label]
                self.update_task_graph_labels( label, line )
                pairs = self.get_dependent_pairs( line )
                for pair in pairs:
                    self.process_dep_pair( pair, cycle_list )

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

        self.loaded = True

    def get_taskdef( self, name, type=None, oneoff=False ):
        coldstart = False
        model_coldstart = False
        if type == 'coldstart':
            coldstart = True
        elif type == 'model coldstart':
            model_coldsdtart = True

        if name not in self['tasks']:
            raise SuiteConfigError, 'task ' + name + ' not defined'
        taskconfig = self['tasks'][name]
        taskd = taskdef.taskdef( name )
        taskd.description = taskconfig['description']
        if not self['ignore task owners']:
            taskd.owner = taskconfig['owner']
        taskd.execution_timeout_minutes = taskconfig['execution timeout minutes']
        taskd.reset_execution_timeout_on_incoming_messages = taskconfig['reset execution timeout on incoming messages']
        if self.dummy_mode:
            # use dummy mode specific job submit method for all tasks
            taskd.job_submit_method = self['dummy mode']['job submission method']
        elif taskconfig['job submission method'] != None:
            # a task-specific job submit method was specified
            taskd.job_submit_method = taskconfig['job submission method']
        else:
            # suite default job submit method
            taskd.job_submit_method = self['job submission method']

        if model_coldstart or coldstart:
            if 'oneoff' not in taskd.modifiers:
                taskd.modifiers.append( 'oneoff' )

        if oneoff:
            if 'oneoff' not in taskd.modifiers:
                taskd.modifiers.append( 'oneoff' )

        taskd.type = taskconfig[ 'type' ]

        for item in taskconfig[ 'type modifier list' ]:
            # TO DO: oneoff not needed here anymore (using dependency graph):
            if item == 'oneoff' or item == 'sequential' or item == 'catchup':
                if item not in taskd.modifiers:
                    taskd.modifiers.append( item )
                continue
            m = re.match( 'model\(\s*restarts\s*=\s*(\d+)\s*\)', item )
            if m:
                taskd.type = 'tied'
                taskd.n_restart_outputs = int( m.groups()[0] )
                continue
            m = re.match( 'clock\(\s*offset\s*=\s*(-{0,1}[\d.]+)\s*hour\s*\)', item )
            if m:
                if 'contact' not in taskd.modifiers:
                    taskd.modifiers.append( 'contact' )
                taskd.contact_offset = m.groups()[0]
                continue
            m = re.match( 'catchup clock\(\s*offset\s*=\s*(\d+)\s*hour\s*\)', item )
            if m:
                if 'catchup_contact' not in taskd.modifiers.append:
                    taskd.modifiers.append( 'catchup_contact' )
                taskd.contact_offset = m.groups()[0]
                continue
            raise SuiteConfigError, 'illegal task type: ' + item

        taskd.logfiles    = taskconfig[ 'log file list' ]
        taskd.commands    = taskconfig[ 'command list' ]
        taskd.environment = taskconfig[ 'environment' ]
        taskd.directives  = taskconfig[ 'directives' ]
        taskd.scripting   = taskconfig[ 'scripting' ]

        return taskd

    def get_task_proxy( self, name, ctime, state, startup ):
        if not self.loaded:
            self.load_taskdefs()
        return self.taskdefs[name].get_task_class()( ctime, state, startup )

    def get_task_class( self, name ):
        if not self.loaded:
            self.load_taskdefs()
        return self.taskdefs[name].get_task_class()
