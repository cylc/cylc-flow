#!/usr/bin/env python

# TO DO: enable loading of graph without loading taskdefs (which is not
# needed when using 'cylc graph' for example).

# TO DO: restore SPECIAL OUTPUTS

import taskdef
import re, os, sys, logging
from mkdir_p import mkdir_p
from validate import Validator
from configobj import get_extra_values
from cylcconfigobj import CylcConfigObj
from registration import registrations
from graphnode import graphnode

try:
    from graphing import pygraphviz
except:
    print "WARNING: pygraphviz is not installed; graphing disabled"
    got_pygraphviz = False
else:
    got_pygraphviz = True

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

class config( CylcConfigObj ):
    def __init__( self, suite=None, dummy_mode=False ):
        self.dummy_mode = dummy_mode
        self.edges = {} # edges[ hour ] = [ [A,B], [C,D], ... ]
        self.taskdefs = {}
        self.loaded = False

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

    #def prerequisite_decrement( self, msg, offset ):
    #    return re.sub( "\$\(CYCLE_TIME\)", "$(CYCLE_TIME - " + offset + ")", msg )

    def __check( self ):
        pass

    def get_title( self ):
        return self['title']

    def get_description( self ):
        return self['description']

    def get_coldstart_task_list( self ):
        # TO DO: automatically determine this by parsing the dependency
        #        graph - requires some thought.
        ##if not self.loaded:
        ##    self.load_tasks()
        ##return self.coldstart_task_list

        # For now user must define this:
        return self['list of tasks required to coldstart the suite']

    def get_task_name_list( self ):
        # return list of task names used in the dependency diagram,
        # not the full tist of defined tasks (self['tasks'].keys())
        if not self.loaded:
            self.load_tasks()
        return self.taskdefs.keys()

    def process_graph_line( self, line, cycle_list_string ):
        # Extract dependent pairs from the suite.rc textual dependency
        # graph to use in constructing graphviz graphs.

        # 'A => B => C'    : [A => B], [B => C]
        # 'A & B => C'     : [A => C], [B => C]
        # 'A => C & D'     : [A => C], [A => D]
        # 'A & B => C & D' : [A => C], [A => D], [B => C], [B => D]

        # '&' Groups aren't really "conditional expressions"; they're
        # equivalent to adding another line:
        #  'A & B => C'
        # is the same as:
        #  'A => C' and 'B => C'

        # '|' (OR) is allowed. For graphing, the final member of an OR
        # group is plotted, by default,
        #  'A | B => C' : [B => C]
        # but a * indicates which member to plot,
        #  'A* | B => C'   : [A => C]
        #  'A & B  | C => D'  : [C => D]
        #  'A & B * | C => D'  : [A => D], [B => D]

        #  An 'or' on the right side is an error:
        #  'A = > B | C'     <--- NOT ALLOWED!

        # NO PARENTHESES ALLOWED FOR NOW, AS IT MAKES PARSING DIFFICULT.
        # But all(?) such expressions that we might need can be
        # decomposed into multiple expressions: 
        #  'A & ( B | C ) => D'               <--- don't use this
        # is equivalent to:
        #  'A => D' and 'B | C => D'          <--- use this instead

        temp = re.split( '\s*,\s*', cycle_list_string )
        # turn cycle_list_string into a list of integer hours
        hours = []
        for i in temp:
            hours.append( int(i) )

        # split on arrows
        sequence = re.split( '\s*=>\s*', line )

        # get list of pairs
        for i in range( 0, len(sequence)-1 ):
            lgroup = sequence[i]
            lconditional = lgroup
            rgroup = sequence[i+1]
            
            # parentheses are used for intercycle dependencies: (T-6) etc.
            # so don't check for them as erroneous conditionals just yet.

            # '|' (OR) is not allowed on the right side
            if re.search( '\|', rgroup ):
                raise SuiteConfigError, "OR '|' conditionals are illegal on the right: " + rgroup

            # split lgroup on OR:
            if re.search( '\|', lgroup ):
                OR_list = re.split('\s*\|\s*', lgroup )
                # if any one is starred, keep it and discard the rest
                found_star = False
                for item in OR_list:
                    if re.search( '\*$', item ):
                        found_star = True
                        lgroup = re.sub( '\*$', '', item )
                        break
                # else keep the right-most member 
                if not found_star:
                    lgroup = OR_list[-1]

            # now split on '&' (AND) and generate corresponding pairs
            rights = re.split( '\s*&\s*', rgroup )
            lefts  = re.split( '\s*&\s*', lgroup )
            for r in rights:
                # unlike graph plotting, taskdefs handle true condtional expressions.
                self.generate_taskdefs( lconditional, r, cycle_list_string )

                for l in lefts:
                    pair = [l,r]
                    # store dependencies by hour
                    for hour in hours:
                        if hour not in self.edges:
                            self.edges[hour] = []
                        if pair not in self.edges[hour]:
                            self.edges[hour].append( pair )

            # self.edges left side members can be:
            #   foo           (task name)
            #   foo:N         (specific output)
            #   foo(T-DD)     (intercycle dep)
            #   foo:N(T-DD)   (both)

    def generate_taskdefs( self, lcond, right, cycle_list_string ):
        # get a list of integer hours from cycle_list_string
        temp = re.split( '\s*,\s*', cycle_list_string )
        hours = []
        for i in temp:
            hours.append( int(i) )

        # extract left side task names (split on '|' or '&')
        lefts = re.split( '\s*[\|&]\s*', lcond )

        # initialise the task definitions
        for node in lefts + [right]:
            name = graphnode( node ).name
            if name not in self.taskdefs:
                self.taskdefs[ name ] = self.get_taskdef( name )
            self.taskdefs[ name ].add_hours( hours )

        # SET TRIGGERS
        if not re.search( '\|', lcond ):
            # lcond is a single trigger, or and '&' only one,
            # in which case we don't need to use conditional 
            # prerequisites (we could, but they may be signficantly less
            # efficient due to use of 'eval'?).
            for left in lefts:
                # strip off '*' plotting conditional indicator
                l = re.sub( '\s*\*', '', left )
                self.taskdefs[right].add_trigger( l, cycle_list_string )
        else:
            # conditional with OR
            # strip off '*' plotting conditional indicator
            l = re.sub( '\s*\*', '', lcond )
            self.taskdefs[right].add_conditional_trigger( l, cycle_list_string )
        
    def get_coldstart_graphs( self ):
        graphs = {}
        if not got_pygraphviz:
            print "config: graphing disabled, install pygraphviz"
            return graphs

        if not self.loaded:
            self.load_tasks()
        for hour in self.edges:
            graphs[hour] = pygraphviz.AGraph(directed=True)
            for pair in self.edges[hour]:
                left, right = pair
                left = left + '(' + str(hour) + ')'
                right = right + '(' + str(hour) + ')'
                graphs[hour].add_edge( left, right )
        return graphs 

    #def get_full_graph( self ):
    #    edges = {}
    #    if not got_pygraphviz:
    #        print "config: graphing disabled, install pygraphviz"
    #        return edges
    #    if not self.loaded:
    #        self.load_tasks()
    #    for cycle_list_string in self['dependency graph']:
    #        for label in self['dependency graph'][ cycle_list_string ]:
    #            line = self['dependency graph'][cycle_list_string][label]
    #            pairs = self.get_dependent_pairs( line )
    #            for cycle in re.split( '\s*,\s*', cycle_list_string ):
    #                print cycle, line
    #                if int(cycle) not in edges:
    #                    edges[ int(cycle) ] = []
    #                for pair in pairs:
    #                    if pair not in edges[int(cycle)]:
    #                        edges[ int(cycle) ].append( pair )
    #
    #    graph = pygraphviz.AGraph(directed=True)
    #    cycles = edges.keys()
    #    cycles.sort()
    #    # note: need list rotation in order to coldstart start at
    #    # another cycle time.
    #    oneoff_done = {}
    #    coldstart_done = False
    #    for cycle in cycles:
    #        for pair in edges[cycle]:
    #            lname = pair.left.name
    #            rname = pair.right.name
    #            type  = pair.type
    #            if 'oneoff' in self.taskdefs[ lname ].modifiers:
    #                if lname in oneoff_done:
    #                    if oneoff_done[lname] != cycle:
    #                        continue
    #                else:
    #                    oneoff_done[lname] = cycle
    #
    #             if coldstart_done and self.taskdefs[ lname ].type == 'tied':
    #                # TO DO: need task-specific prev cycle:
    #               prev = self.prev_cycle( cycle, cycles )
    #                a = lname + '(' + str(prev) + ')'
    #                b = lname + '(' + str(cycle) + ')'
    #                graph.add_edge( a, b )
    #
    #            left = lname + '(' + str(cycle) + ')'
    #            right = rname + '(' + str(cycle) + ')'
    #            graph.add_edge( left, right )
    #        coldstart_done = True
    #    return graph

    def prev_cycle( self, cycle, cycles ):
        i = cycles.index( cycle )
        if i == 0:
            prev = cycles[-1]
        else:
            prev = cycles[i-1]
        return prev

    def load_tasks( self ):
        # LOAD FROM DEPENDENCY GRAPH
        dep_pairs = []

        # loop over cycle time lists
        for section in self['dependency graph']:
            if re.match( '[\s,\d]+', section ):
                cycle_list_string = section
            else:
                continue

            # get a list of integer hours from cycle_list_string
            temp = re.split( '\s*,\s*', cycle_list_string )
            hours = []
            for i in temp:
                hours.append( int(i) )

            # parse the dependency graph for this list of cycle times
            graph = self['dependency graph'][ cycle_list_string ]['graph']
            lines = re.split( '\s*\n\s*', graph )
            for xline in lines:
                # strip comments
                line = re.sub( '#.*', '', xline ) 
                # ignore blank lines
                if re.match( '^\s*$', line ):
                    continue
                # strip leading or trailing spaces
                line = re.sub( '^\s*', '', line )
                line = re.sub( '\s*$', '', line )

                # add to the graphviz dependency graph
                # and generate task proxy class definitions
                self.process_graph_line( line, cycle_list_string )

        # task families
        members = []
        my_family = {}
        for name in self['dependency graph']['task families']:
            self.taskdefs[name].type="family"
            mems = self['dependency graph']['task families'][name]
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

            # check that task names contain only word characters [0-9a-zA-Z_]
            # (use of r'\b' word boundary regex in conditional prerequisites
            # could fail if other characters are allowed).
            if re.search( '[^\w]', name ):
                raise SuiteConfigError, 'Illegal task name: ' + name

        self.loaded = True

    def get_taskdef( self, name, type=None, oneoff=False ):
        if name not in self['tasks']:
            # no [tasks][[name]] section defined: default dummy task
            return taskdef.taskdef(name)

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

        if name in self['dependency graph']['task types']['list of oneoff tasks']:
            taskd.modifiers.append( 'oneoff' )

        if name in self['dependency graph']['task types']['list of sequential tasks']:
            taskd.modifiers.append( 'sequential' )

        taskd.type = 'free'

        # TO DO: clock (contact) tasks
        #m = re.match( 'clock\(\s*offset\s*=\s*(-{0,1}[\d.]+)\s*hour\s*\)', item )
        #    if m:
        #        if 'contact' not in taskd.modifiers:
        #            taskd.modifiers.append( 'contact' )
        #        taskd.contact_offset = m.groups()[0]
        #        continue
        #    m = re.match( 'catchup clock\(\s*offset\s*=\s*(\d+)\s*hour\s*\)', item )
        #    if m:
        #        if 'catchup_contact' not in taskd.modifiers.append:
        #            taskd.modifiers.append( 'catchup_contact' )
        #        taskd.contact_offset = m.groups()[0]
        #        continue
        #    raise SuiteConfigError, 'illegal task type: ' + item

        taskd.logfiles    = taskconfig[ 'list of log files' ]
        taskd.commands    = taskconfig[ 'list of commands' ]
        taskd.environment = taskconfig[ 'environment' ]
        taskd.directives  = taskconfig[ 'directives' ]
        taskd.scripting   = taskconfig[ 'scripting' ]

        return taskd

    def get_task_proxy( self, name, ctime, state, startup ):
        if not self.loaded:
            self.load_tasks()
        return self.taskdefs[name].get_task_class()( ctime, state, startup )

    def get_task_class( self, name ):
        if not self.loaded:
            self.load_tasks()
        return self.taskdefs[name].get_task_class()
