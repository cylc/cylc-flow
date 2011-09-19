#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

# TO DO: document use foo[T-6]:out1, not foo:out1 with $(CYCLE_TIME-6) in
# the explicit output message - so the graph will plot correctly.

# TO DO: document that cylc hour sections must be unique, but can
# overlap: [[[0]]] and [[[0,12]]]; but if the same dependency is 
# defined twice it will result in a "duplicate prerequisite" error.

# NOTE: configobj.reload() apparently does not revalidate (list-forcing
# is not done, for example, on single value lists with no trailing
# comma) ... so to reparse the file  we have to instantiate a new config
# object.

import taskdef
from copy import deepcopy
from OrderedDict import OrderedDict
from cycle_time import ct
import re, os, sys, logging
from mkdir_p import mkdir_p
from validate import Validator
from configobj import get_extra_values, flatten_errors, Section
from cylcconfigobj import CylcConfigObj, ConfigObjError
from graphnode import graphnode, GraphNodeError
from registration import delimiter_re

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
    def __init__( self, l, r, sasl=False, suicide=False, conditional=False ):
        self.left = l
        self.right = r
        self.sasl = sasl
        self.suicide = suicide
        self.conditional = conditional

    def get_right( self, tag, not_first_cycle, raw, startup_only, exclude ):
        # (exclude was briefly used - April 2011 - to stop plotting temporary tasks)
        if self.right in exclude:
            return None
        if self.right == None:
            return None
        first_cycle = not not_first_cycle
        if self.right in startup_only:
            if not first_cycle or raw:
                return None

        # strip off special outputs
        self.right = re.sub( ':\w+', '', self.right )

        return self.right + '%' + str(tag)  # str for int tags (async)

    def get_left( self, tag, not_first_cycle, raw, startup_only, exclude ):
        # (exclude was briefly used - April 2011 - to stop plotting temporary tasks)
        if self.left in exclude:
            return None

        first_cycle = not not_first_cycle

        left = self.left

        # strip off special outputs
        left = re.sub( ':\w+', '', left )

        if re.search( '\[\s*T\s*-(\d+)\s*\]', left ) and first_cycle:
            # ignore intercycle deps in first cycle
            return None

        if left in startup_only:
            if not first_cycle or raw:
                return None

        m = re.search( '(\w+)\s*\[\s*T\s*([+-])(\d+)\s*\]', left )
        if m: 
            left, sign, offset = m.groups()
            # sign must be negative but this is already checked by graphnode processing.
            foo = ct(tag)
            foo.decrement( hours=offset )
            tag = foo.get()
            
        if self.sasl:
            tag = 1

        return left + '%' + str(tag)  # str for int tag (async)

class config( CylcConfigObj ):
    def __init__( self, suite, suiterc, simulation_mode=False, verbose=False ):
        self.simulation_mode = simulation_mode
        self.verbose = verbose
        self.edges = {} # edges[ hour ] = [ [A,B], [C,D], ... ]
        self.taskdefs = {}

        self.async_oneoff_edges = []
        self.async_oneoff_tasks = []
        self.async_repeating_edges = []
        self.async_repeating_tasks = []

        self.family_hierarchy = {}

        self.families_used_in_graph = []

        self.suite = suite
        self.file = suiterc
        self.dir = os.path.dirname(suiterc)

        if not os.path.isfile( self.file ):
            raise SuiteConfigError, 'File not found: ' + self.file

        self.spec = os.path.join( os.environ[ 'CYLC_DIR' ], 'conf', 'suiterc.spec')

        if self.verbose:
            print "LOADING SUITE CONFIG"
        try:
            CylcConfigObj.__init__( self, self.file, configspec=self.spec )
        except ConfigObjError, x:
            raise SuiteConfigError, x

        if self.verbose:
            print "VALIDATING"
        # validate and convert to correct types
        val = Validator()
        test = self.validate( val, preserve_errors=True )
        if test != True:
            # Validation failed
            failed_items = flatten_errors( self, test )
            if self.verbose:
                for item in failed_items:
                    sections, key, result = item
                    print ' ',
                    for sec in sections:
                        print sec, '->',
                    print key
                    if result == False:
                        print "Required item missing."
                    else:
                        print result
            raise SuiteConfigError, "ERROR: suite.rc validation failed"
        
        extras = []
        for sections, name in get_extra_values(self):
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

            # Ignore any entries beginning with "_" so that they can be used for string interpolation
            if not name.startswith( '_' ):
                extra = ' '
                for sec in sections:
                    extra += sec + ' -> '
                extras.append( extra + name )

        if len(extras) != 0:
            for extra in extras:
                print >> sys.stderr, '  ERROR: Illegal entry:', extra 
            raise SuiteConfigError, "ERROR: Illegal suite.rc entry(s) found"

        # parse clock-triggered tasks
        self.clock_offsets = {}
        for item in self['scheduling']['special tasks']['clock-triggered']:
            m = re.match( '(\w+)\s*\(\s*([-+]*\s*[\d.]+)\s*\)', item )
            if m:
                task, offset = m.groups()
                try:
                    self.clock_offsets[ task ] = float( offset )
                except ValueError:
                    raise SuiteConfigError, "ERROR: Illegal clock-trigger offset: " + offset
            else:
                raise SuiteConfigError, "ERROR: Illegal clock-triggered task spec: " + item

        if self.verbose:
            print "PARSING TASK RUNTIMES"
        self.members = {}
        # Parse task config generators. If the runtime section is a list
        # of task names or a list-generating Python expression, then the
        # subsequent config applies to each member. We copy the config
        # section for each member and substitute '$(TASK)' for the
        # actual task name in all items.
        for item in self['runtime']:
            m = re.match( '^Python:(.*)$', item )
            if m:
                # python list-generating expression
                try:
                    task_names = eval( m.groups()[0] )
                except:
                    raise SuiteConfigError, 'Python error: ' + item
            elif re.search( ',', item ):
                # list of task names
                task_names = re.split(', *', item )
            else:
                # a single task name 
                continue
            # generate task configuration for each list member
            for name in task_names:
                # create a new task config section
                tconfig = OrderedDict()
                # specialise it to the actual task
                self.specialize( name, tconfig, self['runtime'][item] )
                # record it under the task name
                self['runtime'][name] = tconfig

            # delete the original multi-task section
            del self['runtime'][item]

        # RUNTIME INHERITANCE
        for label in self['runtime']:
            hierarchy = []
            name = label
            while True:
                hierarchy.append( name )
                inherit = self['runtime'][name]['inherit']
                if inherit:
                    if inherit not in self['runtime']:
                        raise SuiteConfigError, 'Undefined parent runtime: ' + inherit
                        # To allow familes defined implicitly by use in the graph and member
                        # runtime inheritance: 1/ add name to runtime and inherit from root;
                        # 2/ set the hierarchy for name to [name,root]; 3/ add members to
                        # self.members[name]; 4/ add each member to self.members[root].
                    name = inherit
                    if name not in self.members:
                        self.members[name] = []
                    self.members[name].append(label)
                else:
                    #if hierarchy[-1] != 'root':
                    #    hierarchy.append('root')
                    break
            self.family_hierarchy[label] = deepcopy(hierarchy)
            hierarchy.pop() # remove 'root'
            hierarchy.reverse()
            taskconf = self['runtime']['root'].odict()
            for item in hierarchy:
                self.inherit( taskconf, self['runtime'][item] )
            self['runtime'][label] = taskconf

        self.closed_families = self['visualization']['collapsed families']
        for cfam in self.closed_families:
            if cfam not in self.members:
                print >> sys.stderr, 'WARNING, [visualization][collapsed families]: ignoring ' + cfam + ' (not a family)'
                self.closed_families.remove( cfam )
        self.process_directories()
        self.load()
        self.__check_tasks()

    def process_directories(self):
        # Environment variable interpolation in directory paths.
        # (allow use of suite identity variables):
        os.environ['CYLC_SUITE_REG_NAME'] = self.suite
        os.environ['CYLC_SUITE_REG_PATH'] = re.sub( delimiter_re, '/', self.suite )
        os.environ['CYLC_SUITE_DEF_PATH'] = self.dir
        self['cylc']['logging']['directory'] = \
                os.path.expandvars( os.path.expanduser( self['cylc']['logging']['directory']))
        self['cylc']['state dumps']['directory'] =  \
                os.path.expandvars( os.path.expanduser( self['cylc']['state dumps']['directory']))
        self['visualization']['run time graph']['directory'] = \
                os.path.expandvars( os.path.expanduser( self['visualization']['run time graph']['directory']))

        for item in self['runtime']:
            # Local job sub log directories: interpolate all environment variables.
            self['runtime'][item]['job submission']['log directory'] = os.path.expandvars( os.path.expanduser( self['runtime'][item]['job submission']['log directory']))
            # Remote job sub log directories: just suite identity - local variables aren't relevant.
            if self['runtime'][item]['remote']['log directory']:
                for var in ['CYLC_SUITE_REG_PATH', 'CYLC_SUITE_DEF_PATH', 'CYLC_SUITE_REG_NAME']: 
                    self['runtime'][item]['remote']['log directory'] = re.sub( '\${'+var+'}'+r'\b', os.environ[var], self['runtime'][item]['remote']['log directory'])
                    self['runtime'][item]['remote']['log directory'] = re.sub( '\$'+var+r'\b',      os.environ[var], self['runtime'][item]['remote']['log directory'])

    def inherit( self, target, source ):
        for item in source:
            if isinstance( source[item], Section ):
                self.inherit( target[item], source[item] )
            else:
                if source[item]:
                    target[item] = deepcopy(source[item])  # deepcopy for list values

    def specialize( self, name, target, source ):
        # recursively specialize a generator task config section
        # ('source') to a specific config section (target) for task
        # 'name', by replaceing '$(TASK)' with 'name' in all items.
        for item in source:
            if isinstance( source[item], str ):
                # single source item
                target[item] = re.sub( '\$\(TASK\)', name, source[item] )
            elif isinstance( source[item], list ):
                # a list of values 
                newlist = []
                for mem in source[item]:
                    if isinstance( mem, str ):
                        newlist.append( re.sub( '\$\(TASK\)', name, mem ))
                    else:
                        newlist.append( mem )
                target[item] = newlist
            elif isinstance( source[item], Section ):
                # recursive call for to handle a sub-section
                if item not in target:
                    target[item] = OrderedDict()
                self.specialize( name, target[item], source[item] )
            else:
                # boolean or None values
                target[item] = source[item]
                continue

    def set_trigger( self, task_name, output_name=None, offset=None, asyncid_pattern=None ):
        if output_name:
            try:
                trigger = self['runtime'][task_name]['outputs'][output_name]
            except KeyError:
                if output_name == 'fail':
                    trigger = task_name + '%$(TAG) failed'
                else:
                    raise SuiteConfigError, "ERROR: Task '" + task_name + "' does not define output '" + output_name  + "'"
            else:
                # replace $(CYCLE_TIME) with $(TAG) in explicit outputs
                trigger = re.sub( 'CYCLE_TIME', 'TAG', trigger )
        else:
            trigger = task_name + '%$(TAG) succeeded'

        # now adjust for cycle time or tag offset
        if offset:
            trigger = re.sub( 'TAG', 'TAG - ' + str(offset), trigger )
            # extract multiple offsets:
            m = re.match( '(.*)\$\(TAG\s*(.*)\)(.*)', trigger )
            if m:
                pre, combo, post = m.groups()
                combo = eval( combo )
                if combo == 0:
                    trigger = pre + '$(TAG)' + post
                elif combo > 0:
                    trigger = pre + '$(TAG + ' + str(combo) + ')' + post
                else:
                    # '-' appears in combo
                    trigger = pre + '$(TAG ' + str(combo) + ')' + post

        # for oneoff async tasks, replace '$(TAG)' with '1' (NECESS?)
        if task_name in self.async_oneoff_tasks:
            trigger = re.sub( '\$\(TAG\)', '1', trigger )

        if asyncid_pattern:
            trigger = re.sub( '\$\(ASYNCID\)', '(' + asyncid_pattern + ')', trigger )
 
        return trigger

    def __check_tasks( self ):
        # Call after all tasks are defined.
        # Note: 
        #   (a) self['runtime'][name] 
        #       contains the task definition sections of the suite.rc file.
        #   (b) self.taskdefs[name]
        #       contains tasks that will be used, defined by the graph.
        # Tasks (a) may be defined but not used (e.g. commented out of the graph)
        # Tasks (b) may not be defined in (a), in which case they are dummied out.
        for name in self.taskdefs:
            if name not in self['runtime']:
                print >> sys.stderr, 'WARNING: task "' + name + '" is defined only by graph: it inherits the root runtime.'
                self['runtime'][name] = self['runtime']['root'].odict()
 
        #for name in self['runtime']:
        #    if name not in self.taskdefs:
        #        print >> sys.stderr, 'WARNING: runtime "' + name + '" is not used in the graph.'

        # warn if listed special tasks are not defined
        for type in self['scheduling']['special tasks']:
            for name in self['scheduling']['special tasks'][type]:
                if type == 'clock-triggered':
                    name = re.sub('\(.*\)','',name)
                if re.search( '[^0-9a-zA-Z_]', name ):
                    raise SuiteConfigError, 'ERROR: Illegal ' + type + ' task name: ' + name
                if name not in self.taskdefs and name not in self['runtime']:
                    print >> sys.stderr, 'WARNING: ' + type + ' task "' + name + '" is not defined in [tasks] or used in the graph.'

        # TASK INSERTION GROUPS TEMPORARILY DISABLED PENDING USE OF
        # RUNTIME GROUPS FOR INSERTION ETC.
        ### check task insertion groups contain valid tasks
        ##for group in self['task insertion groups']:
        ##    for name in self['task insertion groups'][group]:
        ##        if name not in self['runtime'] and name not in self.taskdefs:
        ##            # This is not an error because it could be caused by
        ##            # temporary commenting out of a task in the graph,
        ##            # and it won't cause catastrophic failure of the
        ##            # insert command.
        ##            print >> sys.stderr, 'WARNING: task "' + name + '" of insertion group "' + group + '" is not defined.'

        # check 'tasks to exclude|include at startup' contains valid tasks
        for name in self['scheduling']['special tasks']['include at start-up']:
                if name not in self['runtime'] and name not in self.taskdefs:
                    raise SuiteConfigError, "ERROR: " + name + ' in "scheduling -> special tasks -> include at start-up" is not defined'
        for name in self['scheduling']['special tasks']['exclude at start-up']:
                if name not in self['runtime'] and name not in self.taskdefs:
                    raise SuiteConfigError, "ERROR: " + name + ' in "scheduling -> special tasks -> exclude at start-up" is not defined'

        # check graphed hours are consistent with [tasks]->[[NAME]]->hours (if defined)
        for name in self.taskdefs:
            # task 'name' is in graph
            if name in self['runtime']:
                # [tasks][name] section exists
                section_hours = [int(i) for i in self['runtime'][name]['hours'] ]
                if len( section_hours ) == 0:
                    # no hours defined in the task section
                    break
                graph_hours = self.taskdefs[name].hours
                bad_hours = []
                for hour in graph_hours:
                    if hour not in section_hours:
                        bad_hours.append(str(hour))
                if len(bad_hours) > 0:
                    raise SuiteConfigError, 'ERROR: [tasks]->[[' + name + ']]->hours disallows the graphed hour(s) ' + ','.join(bad_hours)

        # TO DO: check that any multiple appearance of same task  in
        # 'special tasks' is valid. E.g. a task can be both
        # 'sequential' and 'clock-triggered' at the time, but not both
        # 'model' and 'sequential' at the same time.

    def create_directories( self, task=None ):
        # Create suite log, state, and local job log directories.
        dirs = [ self['cylc']['logging']['directory'], self['cylc']['state dumps']['directory'] ]
        for item in self['runtime']:
            dirs.append( self['runtime'][item]['job submission']['log directory'] )
        for d in dirs:
            mkdir_p( d )
        
    def get_filename( self ):
        return self.file

    def get_dirname( self ):
        return self.dir

    def get_title( self ):
        return self['title']

    def get_description( self ):
        return self['description']

    def get_coldstart_task_list( self ):
        # TO DO: automatically determine this by parsing the dependency graph?
        # For now user must define this:
        return self['scheduling']['special tasks']['cold-start']

    def get_startup_task_list( self ):
        return self['scheduling']['special tasks']['start-up'] + self.async_oneoff_tasks + self.async_repeating_tasks

    def get_task_name_list( self ):
        # return list of task names used in the dependency diagram,
        # not the full list of defined tasks (self['runtime'].keys())
        tasknames = self.taskdefs.keys()
        tasknames.sort(key=str.lower)  # case-insensitive sort
        return tasknames

    def get_asynchronous_task_name_list( self ):
        names = []
        for tn in self.taskdefs:
            if self.taskdefs[tn].type == 'async_repeating' or self.taskdefs[tn].type == 'async_daemon' or self.taskdefs[tn].type == 'async_oneoff':
                names.append(tn)
        names.sort(key=str.lower)
        return names

    def get_full_task_name_list( self ):
        # return list of task names used in the dependency diagram,
        # and task sections (self['runtime'].keys())
        gtasknames = self.taskdefs.keys()
        stasknames = self['runtime'].keys()
        tasknames = {}
        for tn in gtasknames + stasknames:
            if tn not in tasknames:
                tasknames[tn] = True
        all_tasknames = tasknames.keys()
        all_tasknames.sort(key=str.lower)  # case-insensitive sort
        return all_tasknames

    def process_graph_line( self, line, section ):
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

        #  An 'or' on the right side is an error:
        #  'A = > B | C'     <--- NOT ALLOWED!

        # [list of valid hours], or ["once"], or ["ASYNCID:pattern"]
        ttype = None
        validity = []
        if section == "once":
            ttype = 'async_oneoff'
            validity = [section]
        elif re.match( '^ASYNCID:', section ):
            ttype = 'async_repeating'
            validity = [section]
        elif re.match( '^[\s,\d]+$', section ):
            ttype = 'cycling'
            hours = re.split( '\s*,\s*', section )
            for hr in hours:
                hour = int( hr )
                if hour < 0 or hour > 23:
                    raise DefinitionError( 'ERROR: Hour ' + str(hour) + ' must be between 0 and 23' )
                if hour not in validity: 
                    validity.append( hour )
            validity.sort( key=int )
        else:
            raise SuiteConfigError( 'ERROR: Illegal graph validity type: ' + section )

        # REPLACE FAMILY NAMES WITH THE TRUE MEMBER DEPENDENCIES
        for fam in self.members:
            # fam:fail - replace with conditional expressing this:
            # "one or more members failed AND (all members either
            # succeeded or failed)":
            # ( a:fail | b:fail ) & ( a | a:fail ) & ( b|b:fail )
            if re.search( r'\b' + fam + ':fail' + r'\b', line ):
                if fam not in self.families_used_in_graph:
                    self.families_used_in_graph.append(fam)
                mem0 = self.members[fam][0]
                cond1 = mem0 + ':fail'
                cond2 = '( ' + mem0 + ' | ' + mem0 + ':fail )' 
                for mem in self.members[fam][1:]:
                    cond1 += ' | ' + mem + ':fail'
                    cond2 += ' & ( ' + mem + ' | ' + mem + ':fail )'
                cond = '( ' + cond1 + ') & ' + cond2 
                line = re.sub( r'\b' + fam + ':fail' + r'\b', cond, line )
            # fam - replace with members
            if re.search( r'\b' + fam + r'\b', line ):
                if fam not in self.families_used_in_graph:
                    self.families_used_in_graph.append(fam)
                mems = ' & '.join( self.members[fam] )
                line = re.sub( r'\b' + fam + r'\b', mems, line )

        # Split line on dependency arrows.
        tasks = re.split( '\s*=>\s*', line )
        # NOTE:  we currently use only one kind of arrow, but to use
        # several kinds we can split the string like this:
        #     tokens = re.split( '\s*(=[>x])\s*', line ) # a => b =x c
        #     tasks = tokens[0::2]                       # [a, b, c] 
        #     arrow = tokens[1::2]                       # [=>, =x]

        # get list of pairs
        for i in [0] + range( 1, len(tasks)-1 ):
            lexpression = tasks[i]
            if len(tasks) == 1:
                # single node: no rhs group
                rgroup = None
                if re.search( '\|', lexpression ):
                    raise SuiteConfigError, "ERROR: Lone node groups cannot contain OR conditionals: " + lexpression
            else:
                rgroup = tasks[i+1]
           
            if rgroup:
                # '|' (OR) is not allowed on the right side
                if re.search( '\|', rgroup ):
                    raise SuiteConfigError, "ERROR: OR '|' is not legal on the right side of dependencies: " + rgroup

                # (T+/-N) offsets not allowed on the right side (as yet)
                if re.search( '\[\s*T\s*[+-]\s*\d+\s*\]', rgroup ):
                    raise SuiteConfigError, "ERROR: time offsets are not legal on the right side of dependencies: " + rgroup

                # now split on '&' (AND) and generate corresponding pairs
                rights = re.split( '\s*&\s*', rgroup )
            else:
                rights = [None]

            new_rights = []
            for r in rights:
                if r:
                    # ignore output labels on the right (for chained
                    # tasks they are only meaningful on the left)
                    new_rights.append( re.sub( ':\w+', '', r ))
                else:
                    # retain None's in order to handle lone nodes on the left
                    new_rights.append( None )

            rights = new_rights

            # extract task names from lexpression
            nstr = re.sub( '[(|&)]', ' ', lexpression )
            nstr = nstr.strip()
            lnames = re.split( ' +', nstr )

            for rt in rights:
                # foo => '!bar' means task bar should suicide if foo succeeds.
                suicide = False
                if rt and rt.startswith('!'):
                    r = rt[1:]
                    suicide = True
                else:
                    r = rt

                if ttype != 'cycling':
                    for n in lnames + [r]:
                        if not n:
                            continue
                        try:
                            name = graphnode( n ).name
                        except GraphNodeError, x:
                            raise SuiteConfigError, str(x)
                        if ttype == 'async_oneoff':
                            if name not in self.async_oneoff_tasks:
                                self.async_oneoff_tasks.append(name)
                        elif ttype == 'async_repeating': 
                            if name not in self.async_repeating_tasks:
                                self.async_repeating_tasks.append(name)
                
                self.generate_nodes_and_edges( lexpression, lnames, r, ttype, validity, suicide )
                asyncid_pattern = None
                if ttype == 'async_repeating':
                    m = re.match( '^ASYNCID:(.*)$', section )
                    asyncid_pattern = m.groups()[0]
                self.generate_taskdefs( lnames, r, ttype, section, asyncid_pattern )
                self.generate_triggers( lexpression, lnames, r, section, asyncid_pattern, suicide )

    def generate_nodes_and_edges( self, lexpression, lnames, right, ttype, validity, suicide=False ):
        conditional = False
        if re.search( '\|', lexpression ):
            # plot conditional triggers differently
            conditional = True
 
        sasl = False
        for left in lnames:
            if left in self.async_oneoff_tasks + self.async_repeating_tasks:
                sasl = True
            e = edge( left, right, sasl, suicide, conditional )
            if ttype == 'async_oneoff':
                if e not in self.async_oneoff_edges:
                    self.async_oneoff_edges.append( e )
            elif ttype == 'async_repeating':
                if e not in self.async_repeating_edges:
                    self.async_repeating_edges.append( e )
            else:
                for val in validity:
                    if val not in self.edges:
                        self.edges[val] = []
                    if e not in self.edges[val]:
                        self.edges[val].append( e )

    def generate_taskdefs( self, lnames, right, ttype, section, asyncid_pattern ):
        for node in lnames + [right]:
            if not node:
                # if right is None, lefts are lone nodes
                # for which we still define the taskdefs
                continue
            try:
                name = graphnode( node ).name
            except GraphNodeError, x:
                raise SuiteConfigError, str(x)

            if name not in self['runtime']:
                # a task defined by graph only
                # inherit the root runtime
                self['runtime'][name] = self['runtime']['root'].odict()
                if 'root' not in self.members:
                    # (happens when no runtimes are defined in the suite.rc)
                    self.members['root'] = []
                self.family_hierarchy[name] = [name, 'root']
                self.members['root'].append(name)
 
            if name not in self.taskdefs:
                self.taskdefs[ name ] = self.get_taskdef( name )

            # TO DO: setting type should be consolidated to get_taskdef()
            if name in self.async_oneoff_tasks:
                # this catches oneoff async tasks that begin a repeating
                # async section as well.
                self.taskdefs[name].type = 'async_oneoff'
            elif ttype == 'async_repeating':
                self.taskdefs[name].asyncid_pattern = asyncid_pattern
                if name == self['scheduling']['dependencies'][section]['daemon']:
                    self.taskdefs[name].type = 'async_daemon'
                else:
                    self.taskdefs[name].type = 'async_repeating'

            elif ttype == 'cycling':
                self.taskdefs[ name ].set_valid_hours( section )

    def generate_triggers( self, lexpression, lnames, right, section, asyncid_pattern, suicide ):
        if not right:
            # lefts are lone nodes; no more triggers to define.
            return
        ctrig = {}
        for left in lnames:
            lnode = graphnode(left)  # (GraphNodeError checked above)
            if lnode.intercycle:
                self.taskdefs[lnode.name].intercycle = True

            trigger = self.set_trigger( lnode.name, lnode.output, lnode.offset, asyncid_pattern )
            # use fully qualified name for the expression label
            # (task name is not unique, e.g.: "F | F:fail => G")
            label = re.sub( '[-\[\]:]', '_', left )

            ctrig[label] = trigger

        if not re.search( '\|', lexpression ):
            # For single triggers or '&'-only ones, which will be the
            # vast majority, we needn't use conditional prerequisites
            # (they may be less efficient due to python eval at run time).
            for label in ctrig:
                trigger = ctrig[label]
                # using last lnode ...
                if lnode.name in self['scheduling']['special tasks']['start-up'] or \
                        lnode.name in self.async_oneoff_tasks:
                    self.taskdefs[right].add_startup_trigger( trigger, section, suicide )
                elif lnode.name in self.async_repeating_tasks:
                    # TO DO: SUICIDE FOR REPEATING ASYNC
                    self.taskdefs[right].loose_prerequisites.append(trigger)
                else:
                    self.taskdefs[right].add_trigger( trigger, section, suicide )
        else:
            # replace some chars for later use in regular  expressions.
            expr = re.sub( '[-\[\]:]', '_', lexpression )
            # using last lnode ...
            if lnode.name in self['scheduling']['special tasks']['start-up'] or \
                    lnode.name in self.async_oneoff_tasks:
                self.taskdefs[right].add_startup_conditional_trigger( ctrig, expr, section, suicide )
            elif lnode.name in self.async_repeating_tasks:
                # TO DO!!!!
                raise SuiteConfigError, 'ERROR: repeating async task conditionals not done yet'
            else:
                # TO DO: ALSO CONSIDER SUICIDE FOR STARTUP AND ASYNC
                self.taskdefs[right].add_conditional_trigger( ctrig, expr, section, suicide )

    def get_graph( self, start_ctime, stop, colored=True, raw=False,
            group_nodes=[], ungroup_nodes=[], ungroup_recursive=False,
            group_all=False, ungroup_all=False ):

        if group_all:
            for fam in self.members:
                #if fam != 'root':
                if fam not in self.closed_families:
                    self.closed_families.append( fam )

        elif ungroup_all:
            self.closed_families = []

        elif len(group_nodes) > 0:
            for node in group_nodes:
                if node != 'root':
                    parent = self.family_hierarchy[node][1]
                    if parent not in self.closed_families:
                        self.closed_families.append( parent )

        elif len(ungroup_nodes) > 0:
            for node in ungroup_nodes:
                if node in self.closed_families:
                    self.closed_families.remove(node)
                if ungroup_recursive:
                    for fam in deepcopy(self.closed_families):
                        if fam in self.members[node]:
                            self.closed_families.remove(fam)

        if colored:
            graph = graphing.CGraph( self.suite, self['visualization'] )
        else:
            graph = graphing.CGraphPlain( self.suite )

        startup_exclude_list = self.get_coldstart_task_list() + \
                self.get_startup_task_list()

        gr_edges = []

        for e in self.async_oneoff_edges + self.async_repeating_edges:
            right = e.get_right(1, False, False, [], [])
            left  = e.get_left( 1, False, False, [], [])
            nl, nr = self.close_families( left, right )
            gr_edges.append( (nl, nr, False, e.suicide, e.conditional) )
	
        cycles = self.edges.keys()

        if len(cycles) != 0:
            cycles.sort(key=int)
            ctime = start_ctime
            foo = ct( ctime )

            hour = str(int(start_ctime[8:10])) # get string without zero padding
            # TO DO: clean up ctime and hour handling in the following code, down 
            #        to "# sort and then add edges ...". It works, but is messy.
            found = True
            for h in range( int(hour), 24 + int(hour) ):
                diffhrs = h - int(hour)
                if diffhrs > stop:
                    found = False
                    break
                if h > 23:
                   hh = 24 - h
                else:
                   hh = h
                if hh in cycles:
                    foo.increment( hours=diffhrs )
                    break
            if found:
                i = cycles.index(hh)
                ctime = foo.get()
                started = False
                while True:
                    hour = cycles[i]
                    for e in self.edges[hour]:
                        suicide = e.suicide
                        conditional = e.conditional
                        right = e.get_right(ctime, started, raw, startup_exclude_list, [])
                        left  = e.get_left( ctime, started, raw, startup_exclude_list, [])

                        if left == None and right == None:
                            # nothing to add to the graph
                            continue
                        if left != None and not e.sasl:
                            lname, lctime = re.split( '%', left )
                            sct = ct(start_ctime)
                            diffhrs = sct.subtract_hrs( ct(lctime) )
                            if diffhrs > 0:
                                # check that left is not earlier than start time
                                # TO DO: does this invalidate right too?
                                continue
                        else:
                            lname = None
                            lctime = None

                        if right != None:
                            rname, rctime = re.split( '%', right )
                        else:
                            rname = None
                            lctime = None
                        nl, nr = self.close_families( left, right )
                        gr_edges.append( ( nl, nr, False, e.suicide, e.conditional ) )

                    # next cycle
                    started = True
                    if i == len(cycles) - 1:
                        i = 0
                        diff = 24 - int(hour) + int(cycles[0])
                    else:
                        i += 1
                        diff = int(cycles[i]) - int(hour)

                    foo = ct(ctime)
                    foo.increment( hours=diff )
                    ctime = foo.get()
                    diffhrs = foo.subtract_hrs( ct(start_ctime) )
                    if diffhrs > int(stop):
                        break
                
        # sort and then add edges in the hope that edges added in the
        # same order each time will result in the graph layout not
        # jumping around (does this help? -if not discard)
        gr_edges.sort()
        for e in gr_edges:
            l, r, dashed, suicide, conditional = e
            if l== None and r == None:
                pass
            elif l == None:
                graph.add_node( r )
            elif r == None:
                graph.add_node( l )
            else:
                style=None
                arrowhead='normal'
                if dashed:
                    style='dashed'
                if suicide:
                    style='dashed'
                    arrowhead='dot'
                if conditional:
                    arrowhead='onormal'
                graph.add_edge( l, r, False, style=style, arrowhead=arrowhead )

        for n in graph.nodes():
            if not colored:
                n.attr['style'] = 'filled'
                n.attr['fillcolor'] = 'cornsilk'

        return graph

    def close_families( self, nl, nr ):
        # Replace family members with family nodes if requested.
        lname, ltag = None, None
        rname, rtag = None, None
        if nl:
            lname, ltag = nl.split('%')
        if nr:
            rname, rtag = nr.split('%')

        # for nested families, only consider the outermost one
        clf = deepcopy( self.closed_families )
        for i in self.closed_families:
            for j in self.closed_families:
                if i in self.members[j]:
                    # i is a member of j
                    if i in clf:
                        clf.remove( i )

        for fam in clf:
            if lname in self.members[fam] and rname in self.members[fam]:
                # l and r are both members of fam
                #nl, nr = None, None  # this makes 'the graph disappear if grouping 'root'
                nl,nr = fam + '%'+ltag, fam + '%'+rtag
                break
            elif lname in self.members[fam]:
                # l is a member of fam
                nl = fam + '%'+ltag
            elif rname in self.members[fam]:
                # r is a member of fam
                nr = fam + '%'+rtag
        return nl, nr

    def prev_cycle( self, cycle, cycles ):
        i = cycles.index( cycle )
        if i == 0:
            prev = cycles[-1]
        else:
            prev = cycles[i-1]
        return prev

    def load( self ):
        if self.verbose:
            print 'PARSING SUITE GRAPH'
        # parse the suite dependencies section
        for item in self['scheduling']['dependencies']:
            if item == 'graph':
                # One-off asynchronous tasks.
                section = "once"
                graph = self['scheduling']['dependencies']['graph']
                if graph == None:
                    # this means no async_oneoff tasks defined
                    continue
            else:
                section = item
                try:
                    graph = self['scheduling']['dependencies'][item]['graph']
                except IndexError:
                    raise SuiteConfigError, 'Missing graph string in [scheduling][dependencies]['+item+']'

            # split the graph string into successive lines
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

                items = []
                m = re.match( '^Python:(.*)$', line )
                if m:
                    # python list-generating expression
                    # treat each member as a separate graph line
                    try:
                        items = eval(m.groups()[0])
                    except:
                        raise SuiteConfigError, 'Python error: ' + line
                else:
                    items = [line]
 
                for item in items:
                    # generate pygraphviz graph nodes and edges, and task definitions
                    self.process_graph_line( item, section )

        # sort hours list for each task
        for name in self.taskdefs:
            self.taskdefs[name].hours.sort( key=int ) 

    def get_taskdef( self, name, strict=False ):
        try:
            taskd = taskdef.taskdef( name )
        except taskdef.DefinitionError, x:
            raise SuiteConfigError, str(x)

        # SET ONE OFF TASK INDICATOR
        #   cold start and startup tasks are automatically one off
        if name in self['scheduling']['special tasks']['one-off'] or \
            name in self['scheduling']['special tasks']['start-up'] or \
            name in self['scheduling']['special tasks']['cold-start']:
                taskd.modifiers.append( 'oneoff' )

        # SET SEQUENTIAL TASK INDICATOR
        if name in self['scheduling']['special tasks']['sequential']:
            taskd.modifiers.append( 'sequential' )

        # SET MODEL TASK INDICATOR
        # (TO DO - can we identify these tasks from the graph?)
        elif name in self['scheduling']['special tasks']['explicit restart outputs']:
            taskd.type = 'tied'
        else:
            taskd.type = 'free'

        # SET CLOCK-TRIGGERED TASKS
        if name in self.clock_offsets:
            taskd.modifiers.append( 'clocktriggered' )
            taskd.clocktriggered_offset = self.clock_offsets[name]

        # get the task runtime
        taskconfig = self['runtime'][name]
        taskd.description = taskconfig['description']

        for lbl in taskconfig['outputs']:
            # replace $(CYCLE_TIME) with $(TAG) in explicit outputs
            taskd.outputs.append( re.sub( 'CYCLE_TIME', 'TAG', taskconfig['outputs'][lbl] ))

        taskd.owner = taskconfig['remote']['owner']

        if self.simulation_mode:
            taskd.job_submit_method = self['cylc']['simulation mode']['job submission method']
            taskd.commands = self['cylc']['simulation mode']['command scripting']
        else:
            taskd.job_submit_method = taskconfig['job submission']['method']
            taskd.commands   = taskconfig['command scripting']
            taskd.precommand = taskconfig['pre-command scripting'] 
            taskd.postcommand = taskconfig['post-command scripting'] 

        taskd.job_submission_shell = taskconfig['job submission']['job script shell']

        taskd.job_submit_command_template = taskconfig['job submission']['command template']

        taskd.job_submit_log_directory = taskconfig['job submission']['log directory']
        # this is only used locally, so interpolate environment variables out now:

        # Remotely hosted tasks
        if taskconfig['remote']['host'] or taskconfig['remote']['owner']:
            taskd.remote_host = taskconfig['remote']['host']
            if not taskconfig['remote']['cylc directory']:
                raise SuiteConfigError, name + ": remote tasks must specify the remote cylc directory"

            taskd.remote_shell_template = taskconfig['remote']['remote shell template']
            taskd.remote_cylc_directory = taskconfig['remote']['cylc directory']
            taskd.remote_suite_directory = taskconfig['remote']['suite definition directory']
            if not taskconfig['remote']['log directory']:
                taskd.remote_log_directory  = re.sub( os.environ['HOME'] + '/', '', taskd.job_submit_log_directory )
            else:
                taskd.remote_log_directory  = taskconfig['remote']['log directory']

        taskd.manual_messaging = taskconfig['manual task completion messaging']

        # task-specific event hook scripts
        taskd.hook_scripts[ 'submitted' ]         = taskconfig['task event hook scripts']['submitted']
        taskd.hook_scripts[ 'submission failed' ] = taskconfig['task event hook scripts']['submission failed']
        taskd.hook_scripts[ 'started'   ]         = taskconfig['task event hook scripts']['started'  ]
        taskd.hook_scripts[ 'warning'   ]         = taskconfig['task event hook scripts']['warning'  ]
        taskd.hook_scripts[ 'succeeded' ]         = taskconfig['task event hook scripts']['succeeded' ]
        taskd.hook_scripts[ 'failed'    ]         = taskconfig['task event hook scripts']['failed'   ]
        taskd.hook_scripts[ 'timeout'   ]         = taskconfig['task event hook scripts']['timeout'  ]
        # task-specific timeout hook scripts
        taskd.timeouts[ 'submission'    ]     = taskconfig['task event hook scripts']['submission timeout in minutes']
        taskd.timeouts[ 'execution'     ]     = taskconfig['task event hook scripts']['execution timeout in minutes' ]
        taskd.timeouts[ 'reset on incoming' ] = taskconfig['task event hook scripts']['reset execution timeout on incoming messages']

        taskd.logfiles    = taskconfig[ 'extra log files' ]
        taskd.environment = taskconfig[ 'environment' ]
        taskd.directives  = taskconfig[ 'directives' ]

        return taskd

    def get_task_proxy( self, name, ctime, state, stopctime, startup ):
        # get a proxy for a task in the dependency graph.
        return self.taskdefs[name].get_task_class()( ctime, state, stopctime, startup )

    def get_task_proxy_raw( self, name, ctime, state, stopctime,
            startup, test=False, strict=True ):
        # GET A PROXY FOR A TASK THAT IS NOT GRAPHED - i.e. call this
        # only if get_task_proxy() raises a KeyError.

        # This allows us to 'cylc submit' single tasks that are defined
        # in suite.rc but not in the suite graph.  Because the graph
        # defines valid cycle times, however, we must use
        # [tasks][[name]]hours or, if the hours entry is not defined,
        # assume that the requested ctime is valid for the task.
        td = self.get_taskdef( name, strict=True )
        chour = int(ctime[8:10])
        hours = self['runtime'][name]['hours']
        if len(hours) == 0:
            # no hours defined; instantiation will fail unless we assume
            # the test hour is valid.
            if strict:
                # you cannot insert into a running suite a task that has
                # no hours defined (what would the cycle time of its
                # next instance be?).
                raise SuiteConfigError, name + " has no hours defined in graph or [tasks]"
            if test:
                # used by the 'cylc validate' command
                # THIS IS NOW PROBABLY A RUNTIME GROUP, NOT A TASK.
                #print >> sys.stderr, "WARNING: no hours in graph or runtime; task can only be used with 'cylc submit'."
                pass
            else:
                # if 'submit'ed alone:
                print >> sys.stderr, "WARNING: " + name + ": no hours in graph or runtime; task can only be used with 'cylc submit'."
                print >> sys.stderr, "WARNING: " + name + ": no hours defined - task will be submitted with the exact cycle time " + ctime
            td.hours = [ chour ]
        else:
            td.hours = [ int(i) for i in hours ]
        tdclass = td.get_task_class()( ctime, 'waiting', startup, stopctime )
        return tdclass

    def get_task_class( self, name ):
        return self.taskdefs[name].get_task_class()
