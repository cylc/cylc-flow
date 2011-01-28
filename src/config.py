#!/usr/bin/env python

# TO DO: catchup contact
# TO DO: ERROR CHECKING:
#        - MULTIPLE DEFINITION OF SAME PREREQUISITES, E.G. VIA TWO
#          CYCLE-TIME SECTIONS IN THE GRAPH.
#        - SPECIAL OUTPUTS - check ':foo' is defined in task section
#          - check outputs do not appear on right side of pairs, 
#          - OR IGNORE  IF THEY DO?

# IMPORTANT NOTE: configobj.reload() apparently does not revalidate
# (list-forcing is not done, for example, on single value lists with
# no trailing comma) ... so to reparse the file  we have to instantiate
# a new config object.

import taskdef
import cycle_time
import re, os, sys, logging
from mkdir_p import mkdir_p
from validate import Validator
from configobj import get_extra_values
from cylcconfigobj import CylcConfigObj
from registration import registrations
from graphnode import graphnode

try:
    import graphing
except:
    graphing_disabled = True
else:
    graphing_disabled = False

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

class edge( object):
    def __init__( self, l, r ):
        self.left_group = l
        self.right = r

    def get_right( self, ctime, not_first_cycle, raw, startup_only ):
        first_cycle = not not_first_cycle
        if self.right in startup_only:
            if not first_cycle or raw:
                return None
        return self.right + '%' + ctime

    def get_left( self, ctime, not_first_cycle, raw, startup_only ):
        #if re.search( '\|', self.left_group ):
        OR_list = re.split('\s*\|\s*', self.left_group )

        first_cycle = not not_first_cycle

        options = []
        starred_index = -1
        for item in OR_list:
            # strip off special outputs
            item = re.sub( ':\w+', '', item )

            starred = False
            if re.search( '\*$', item ):
                starred = True
                item = re.sub( '\*$', '', item )

            m = re.search( '(\w+)\s*\(\s*T\s*-(\d+)\s*\)', item )
            if m: 
                if first_cycle:
                    # ignore intercycle
                    continue
                else:
                    # not first cycle
                    options.append( item )
                    if starred:
                        starred_index = len(options)-1
                    continue

            if item in startup_only:
                if not first_cycle:
                    continue
                else:
                    # first cycle
                    if not raw:
                        options.append( item )
                        if starred:
                            starred_index = len(options)-1
                        continue
            else:
                options.append( item )
                if starred:
                    starred_index = len(options)-1
                continue

        if len(options) == 0:
            return None

        if starred_index != -1:
            left = options[ starred_index ]
        else:
            #rightmost item
            left = options[-1]

        m = re.search( '(\w+)\s*\(\s*T\s*-(\d+)\s*\)', left )
        if m: 
            task = m.groups()[0]
            offset = m.groups()[1]
            ctime = cycle_time.decrement( ctime, offset )
            res = task + '%' + ctime
        else:
            res = left + '%' + ctime
            
        return res

class config( CylcConfigObj ):
    def __init__( self, suite=None, dummy_mode=False ):
        self.dummy_mode = dummy_mode
        self.edges = {} # edges[ hour ] = [ [A,B], [C,D], ... ]
        self.taskdefs = {}
        self.loaded = False
        self.graph_loaded = False

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
        
        found_extra = False
        for sections, name in get_extra_values(self):
            # TEMPORARY
            print 'Unspec\'d item ERROR:', sections, name
            # !!! TO DO: THE FOLLOWING FROM CONFIGOBJ DOC SECTION 15.1 FAILS 
            ### this code gets the extra values themselves
            ##the_section = self
            ##for section in sections:
            ##    the_section = self[section]   #<------!!! KeyError !!!
            ### the_value may be a section or a value
            ##the_value = the_section[name]
            ##section_or_value = 'value'
            ##if isinstance(the_value, dict):
            ##    # Sections are subclasses of dict
            ##    section_or_value = 'section'
          
            ##section_string = ', '.join(sections) or "top level"
            ##print 'Extra entry in section: %s. Entry %r is a %s' % (section_string, name, section_or_value)
            found_extra = True
        
        if found_extra:
            raise SuiteConfigError, "Illegal suite.rc entry found"

        # check cylc-specific self consistency
        self.__check()

        self.process_configured_directories()

        # parse clock-triggered tasks
        self.clock_offsets = {}
        for item in self['special tasks']['clock-triggered']:
            m = re.match( '(\w+)\s*\(\s*([-+]*\s*[\d.]+)\s*\)', item )
            if m:
                task, offset = m.groups()
                try:
                    self.clock_offsets[ task ] = float( offset )
                except ValueError:
                    raise SuiteConfigError, "Illegal clock-trigger offset: " + offset
            else:
                raise SuiteConfigError, "Illegal clock-triggered task spec: " + item

        # parse families
        self.member_of = {}
        self.members = {}
        for fam in self['task families']:
            self.members[ fam ] = self['task families'][fam]
            for task in self['task families'][fam]:
                self.member_of[ task ] = fam

    def check_tasks( self ):
        # call after all tasks are defined, to check for undefined
        # tasks and tasks that are defined but not used.
        for name in self.taskdefs:
            if name not in self['tasks']:
                print >> sys.stderr, 'WARNING: task ' + name + ' is defined by graph only.'
        for name in self['tasks']:
            if name not in self.taskdefs:
                print >> sys.stderr, 'WARNING: task ' + name + ' is defined but not used.'
        # warn if listed special tasks are not defined
        for type in self['special tasks']:
            for name in self['special tasks'][type]:
                if type == 'clock-triggered':
                    name = re.sub('\(.*\)','',name)
                if name not in self['tasks']:
                    # No [tasks][[name]] section
                    if name not in self.taskdefs and name not in self['tasks']:
                        print >> sys.stderr, 'WARNING: ' + type + ' task ' + name + ' is not defined.'

    def process_configured_directories( self ):
        # allow $CYLC_SUITE_NAME in job submission log directory
        jsld = self['job submission log directory' ] 
        jsld = re.sub( '\${CYLC_SUITE_NAME}', self.suite, jsld )
        jsld = re.sub( '\$CYLC_SUITE_NAME', self.suite, jsld )

        # Make directories relative to $HOME or $CYLC_SUITE_DIR,
        # unless specified as absolute paths already.
        self['top level logging directory'] = self.make_dir_absolute( self['top level logging directory'], home=True )
        self['top level state dump directory'] = self.make_dir_absolute( self['top level state dump directory'], home=True )
        self['job submission log directory' ] = self.make_dir_absolute( jsld, home=True )
        self['visualization']['run time graph directory'] = self.make_dir_absolute( self['visualization']['run time graph directory'] )
        self['experimental']['live graph directory path'] = self.make_dir_absolute( self['experimental']['live graph directory path'] )

    def make_dir_absolute( self, indir, home=False ):
        # make dir relative to $HOME or $CYLC_SUITE_DIR unless already absolute.
        if re.match( '^/', indir ):
            # already absolute
            return indir
        if home:
            prefix = os.environ['HOME']
        else:
            prefix = self.dir
        return os.path.join( prefix, indir )

    def create_directories( self ):
        # create logging, state, and job log directories if necessary
        for dir in [
            self['top level logging directory'], 
            self['top level state dump directory'],
            self['job submission log directory'],
            self['visualization']['run time graph directory'] ]: 
            mkdir_p( dir )
        if self['experimental']['write live graph']:
            mkdir_p( self['experimental']['live graph directory path'] )

    def get_filename( self ):
        return self.file

    def get_dirname( self ):
        return self.dir

    def __check( self ):
        pass

    def get_title( self ):
        return self['title']

    def get_description( self ):
        return self['description']

    def get_coldstart_task_list( self ):
        # TO DO: automatically determine this by parsing the dependency
        #        graph - requires some thought.
        # For now user must define this:
        return self['special tasks']['coldstart']

    def get_startup_task_list( self ):
        return self['special tasks']['startup']

    def get_task_name_list( self ):
        # return list of task names used in the dependency diagram,
        # not the full tist of defined tasks (self['tasks'].keys())
        if not self.loaded:
            self.load_tasks()
        tasknames = self.taskdefs.keys()
        tasknames.sort(key=str.lower)  # case-insensitive sort
        return tasknames

    def edges_from_graph_line( self, line, cycle_list_string ):
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
            rgroup = sequence[i+1]
            
            # parentheses are used for intercycle dependencies: (T-6) etc.
            # so don't check for them as erroneous conditionals just yet.

            # '|' (OR) is not allowed on the right side
            if re.search( '\|', rgroup ):
                raise SuiteConfigError, "OR '|' conditionals are illegal on the right: " + rgroup

            # now split on '&' (AND) and generate corresponding pairs
            rights = re.split( '\s*&\s*', rgroup )
            lefts  = re.split( '\s*&\s*', lgroup )
            for r in rights:
                for l in lefts:
                    e = edge( l,r )
                    # store edges by hour
                    for hour in hours:
                        if hour not in self.edges:
                            self.edges[hour] = []
                        if e not in self.edges[hour]:
                            self.edges[hour].append( e )

            # self.edges left side members can be:
            #   foo           (task name)
            #   foo:N         (specific output)
            #   foo(T-DD)     (intercycle dep)
            #   foo:N(T-DD)   (both)


    def tasks_from_graph_line( self, line, cycle_list_string ):
        # Extract dependent pairs from the suite.rc textual dependency
        # graph and use to defined task proxy class definitions.

        # SEE DOCUMENTATION OF GRAPH LINE FORMAT ABOVE

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

            # now split on '&' (AND) and generate corresponding pairs
            rights = re.split( '\s*&\s*', rgroup )
            for r in rights:
                self.generate_taskdefs( lconditional, r, cycle_list_string )

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
            # lcond is a single trigger, or an '&'-only one, in which
            # case we don't need to use conditional prerequisites (we
            # could, but they may be less # efficient due to 'eval'?).

            for left in lefts:
                # strip off '*' plotting conditional indicator
                l = re.sub( '\s*\*', '', left )

                lnode = graphnode( l )
                if lnode.name in self['special tasks']['startup']:
                    self.taskdefs[right].add_startup_trigger( l, cycle_list_string )
                else:
                    if lnode.intercycle:
                        self.taskdefs[lnode.name].intercycle = True
                    if lnode.special_output:
                        output = self['tasks'][lnode.name]['outputs'][lnode.output]
                        self.taskdefs[right].add_special_trigger( output, cycle_list_string )
                    else:
                        self.taskdefs[right].add_trigger( l, cycle_list_string )
        else:
            # Conditional with OR:
            # Strip off '*' plotting conditional indicator
            l = re.sub( '\s*\*', '', lcond )

            # A startup task currently cannot be part of a conditional
            # (to change this, need add_startup_conditional_trigger()
            # similarly to above to non-conditional ... and follow
            # through in taskdef.py).
            for t in self['special tasks']['startup']:
                if re.search( r'\b' + t + r'\b', l ):
                    raise SuiteConfigError, 'ERROR: startup task in conditional: ' + t
            self.taskdefs[right].add_conditional_trigger( l, cycle_list_string )
            lefts = re.split( '\s*[\|&]\s*', l)

            for left in lefts:
                lnode = graphnode(left)
                if lnode.intercycle:
                    self.taskdefs[lnode.name].intercycle = True

    def get_graph( self, start_ctime, stop, colored=True, raw=False ):
        # check if graphing is disabled in the calling method
        hour = int( start_ctime[8:10] )
        if not self.graph_loaded:
            self.load_graph()
        if colored:
            graph = graphing.CGraph( self.suite, self['visualization'] )
        else:
            graph = graphing.CGraphPlain( self.suite )

        cycles = self.edges.keys()
        cycles.sort()
        ctime = start_ctime
        i = cycles.index( hour )
        started = False

        exclude_list = self.get_coldstart_task_list() + self.get_startup_task_list()

        gr_edges = []

        while True:
            hour = cycles[i]
            for e in self.edges[hour]:
                right = e.get_right(ctime, started, raw, exclude_list )
                left  = e.get_left( ctime, started, raw, exclude_list )
                if left == None or right == None:
                    continue

                if self['visualization']['show family members']:
                    lname, lctime = re.split( '%', left )
                    rname, rctime = re.split( '%', right )
                    if lname in self.members and rname in self.members:
                        # both families
                        for lmem in self.members[lname]:
                            for rmem in self.members[rname]:
                                lmemid = lmem + '%' + lctime
                                rmemid = rmem + '%' + rctime
                                gr_edges.append( (lmemid, rmemid ) )
                    elif lname in self.members:
                        # left family
                        for mem in self.members[lname]:
                            memid = mem + '%' + lctime
                            gr_edges.append( (memid, right ) )
                    elif rname in self.members:
                        # right family
                        for mem in self.members[rname]:
                            memid = mem + '%' + rctime
                            gr_edges.append( (left, memid ) )
                    else:
                        # no families
                        gr_edges.append( (left, right) )
                else:
                    gr_edges.append( (left, right) )

            # next cycle
            started = True
            if i == len(cycles) - 1:
                i = 0
                diff = 24 - hour + cycles[0]
            else:
                i += 1
                diff = cycles[i] - hour
            ctime = cycle_time.increment( ctime, diff )

            if int( cycle_time.diff_hours( ctime, start_ctime )) >= int(stop):
                break
                
        # sort and then add edges in the hope that edges added in the
        # same order each time will result in the graph layout not
        # jumping around (does it work ...?)
        gr_edges.sort()
        for e in gr_edges:
            l, r = e
            graph.add_edge( l, r )

        return graph

    def prev_cycle( self, cycle, cycles ):
        i = cycles.index( cycle )
        if i == 0:
            prev = cycles[-1]
        else:
            prev = cycles[i-1]
        return prev

    def load_graph( self ):
        # LOAD graph edges FROM DEPENDENCY GRAPH
        dep_pairs = []

        # loop over cycle time lists
        for section in self['dependencies']:
            if re.match( '[\s,\d]+', section ):
                cycle_list_string = section
            else:
                raise SuiteConfigError, 'Illegal Section: [dependencies]['+section+']'

            # get a list of integer hours from cycle_list_string
            temp = re.split( '\s*,\s*', cycle_list_string )
            hours = []
            for i in temp:
                hours.append( int(i) )

            # parse the dependency graph for this list of cycle times
            graph = self['dependencies'][ cycle_list_string ]['graph']
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
                self.edges_from_graph_line( line, cycle_list_string )

        self.graph_loaded = True

    def load_tasks( self ):
        # LOAD FROM DEPENDENCY GRAPH
        dep_pairs = []

        # loop over cycle time lists
        for section in self['dependencies']:
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
            graph = self['dependencies'][ cycle_list_string ]['graph']
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
                self.tasks_from_graph_line( line, cycle_list_string )

        # task families
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

            # check that task names contain only word characters [0-9a-zA-Z_]
            # (use of r'\b' word boundary regex in conditional prerequisites
            # could fail if other characters are allowed).
            if re.search( '[^\w]', name ):
                raise SuiteConfigError, 'Illegal task name: ' + name

        self.check_tasks()
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

        # SET ONEOFF TASK INDICATOR
        #   coldstart and startup tasks are automatically oneoff
        if name in self['special tasks']['oneoff'] or \
            name in self['special tasks']['startup'] or \
            name in self['special tasks']['coldstart']:
            taskd.modifiers.append( 'oneoff' )

        # SET SEQUENTIAL TASK INDICATOR
        if name in self['special tasks']['sequential']:
            taskd.modifiers.append( 'sequential' )

        # ONLY USING FREE TASK FOR NOW (MODELS MUST BE SEQUENTIAL)
        taskd.type = 'free'

        # SET CLOCK-TRIGGERED TASKS
        if name in self.clock_offsets:
            taskd.modifiers.append( 'contact' )
            taskd.contact_offset = self.clock_offsets[name]

        for lbl in self['tasks'][name]['outputs']:
            taskd.outputs.append( self['tasks'][name]['outputs'][lbl] )

        taskd.logfiles    = taskconfig[ 'extra log files' ]
        taskd.commands    = taskconfig[ 'command' ]
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
