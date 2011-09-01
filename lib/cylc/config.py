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

# TO DO: check for multiple definition of same prerequisites, e.g. via
# two cycle-time sections in the graph.
# TO DO: document use foo(T-6):out1, not foo:out1 with $(CYCLE_TIME-6) in
# the explicit output message - so the graph will plot correctly.

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
from registration import getdb, regsplit, RegistrationError
from graphnode import graphnode, GraphNodeError

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
            if sign != '-':
                # TO DO: this check is redundant (already checked by graphnode processing).
                raise SuiteConfigError, "Prerequisite offsets must be negative: " + left
            foo = ct(tag)
            foo.decrement( hours=offset )
            tag = foo.get()
            
        if self.sasl:
            tag = 1

        return left + '%' + str(tag)  # str for int tag (async)


def get_rcfiles ( suite ):
    # return a list of all rc files for this suite
    # (i.e. suite.rc plus any include-files it uses).
    rcfiles = []
    try:
        reg = getdb( suite )
        reg.load_from_file()
        dir, descr = reg.get( suite )
    except RegistrationError, x:
        raise SuiteConfigError(str(x))
    suiterc = os.path.join( dir, 'suite.rc' )
    rcfiles.append( suiterc )
    for line in open( suiterc, 'rb' ):
        m = re.match( '^\s*%include\s+([\/\w\-\.]+)', line )
        if m:
            rcfiles.append(os.path.join( dir, m.groups()[0]))
    return rcfiles

def get_suite_title( suite=None, path=None ):
    # cheap suite title extraction for use by the registration
    # database commands - uses very minimal parsing of suite.rc
    if suite:
        try:
            reg = getdb( suite )
            reg.load_from_file()
            dir, descr = reg.get( suite )
        except RegistrationError, x:
            raise SuiteConfigError(str(x))
        file = os.path.join( dir, 'suite.rc' )
    elif path:
        # allow load by path so that suite title can be parsed for
        # new suite registrations.
        suite = '(None)'
        file = os.path.join( path, 'suite.rc' )
    else:
        raise SuiteConfigError, 'ERROR, config.get_suite_title(): suite registration or path required'

    if not os.path.isfile( file ):
        raise SuiteConfigError, 'File not found: ' + file

    found = False
    for line in open( file, 'rb' ):
        m = re.match( '^\s*title\s*=\s*(.*)$', line )
        if m:
            title = m.groups()[0]
            # strip trailing space
            title = title.rstrip()
            # NOTE: ANY TRAILING COMMENT WILL BE INCLUDED IN THE TITLE
            #     (but this doesn't really matter for our purposes)
            # (stripping isn't trivial in general - what about strings?)
            found = True
            break

    if not found:
        print >> sys.stderr, 'WARNING: ' + suite + ' title not found by suite.rc search - doing full parse.'
        # This means the title is defined in a suite.rc include-file, or
        # is not defined. In the latter case, a full parse will result
        # in the default title being used (from conf/suiterc.spec). 
        try:
            if path:
                title = config( path=path ).get_title()
            else:
                title = config( suite ).get_title()
        except SuiteConfigError, x:
            print >> sys.stderr, 'ERROR: suite.rc parse failure!'
            raise SystemExit( str(x) )

    return title

class config( CylcConfigObj ):
    def __init__( self, suite=None, simulation_mode=False, path=None ):
        self.simulation_mode = simulation_mode
        self.edges = {} # edges[ hour ] = [ [A,B], [C,D], ... ]
        self.taskdefs = {}
        self.tasks_loaded = False
        self.graph_loaded = False

        self.async_oneoff_edges = []
        self.async_oneoff_tasks = []
        self.async_repeating_edges = []
        self.async_repeating_tasks = []

        if suite:
            self.suite = suite
            try:
                reg = getdb( suite )
                reg.load_from_file()
                self.dir, descr = reg.get( suite )
            except RegistrationError, x:
                raise SuiteConfigError(str(x))
            self.file = os.path.join( self.dir, 'suite.rc' )
        elif path:
            # allow load by path so that suite title can be parsed for
            # new suite registrations.
            self.suite = 'fooWx_:barWx_'
            self.dir = path
            self.file = os.path.join( path, 'suite.rc' )
        elif 'CYLC_SUITE' in os.environ:
            self.suite = os.environ[ 'CYLC_SUITE' ]
            self.file = os.path.join( os.environ[ 'CYLC_SUITE_DIR' ], 'suite.rc' ),
        else:
            raise SuiteConfigError, 'ERROR: Suite Undefined'

        if not os.path.isfile( self.file ):
            raise SuiteConfigError, 'File not found: ' + self.file

        # now export CYLC_SUITE, CYLC_SUITE_GROUP, and CYLC_SUITE_NAME
        # to the local environment so that these variables can be used
        # in directories defined in the suite config file (see use of 
        # os.path.expandvars() below).
        cylc_suite_owner, cylc_suite_group, cylc_suite_name = regsplit( self.suite ).get()
        os.environ['CYLC_SUITE'] = self.suite
        os.environ['CYLC_SUITE_GROUP' ] = cylc_suite_group
        os.environ['CYLC_SUITE_NAME'  ] = cylc_suite_name
        os.environ['CYLC_SUITE_DIR'   ] = self.dir

        self.spec = os.path.join( os.environ[ 'CYLC_DIR' ], 'conf', 'suiterc.spec')

        # load config
        try:
            CylcConfigObj.__init__( self, self.file, configspec=self.spec )
        except ConfigObjError, x:
            raise SuiteConfigError, x

        # validate and convert to correct types
        val = Validator()
        test = self.validate( val, preserve_errors=True )
        if test != True:
            # Validation failed
            failed_items = flatten_errors( self, test )
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
            extra = ' '
            for sec in sections:
                extra += sec + ' -> '
            extras.append( extra + name )
        
        if len(extras) != 0:
            for extra in extras:
                print >> sys.stderr, '  ERROR: Illegal entry:', extra 
            raise SuiteConfigError, "ERROR: Illegal suite.rc entry(s) found"

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
                    raise SuiteConfigError, "ERROR: Illegal clock-trigger offset: " + offset
            else:
                raise SuiteConfigError, "ERROR: Illegal clock-triggered task spec: " + item

        # parse families
        self.member_of = {}
        self.members = {}
        for fam in self['task families']:
            members = []
            for mem in self['task families'][fam]:
                m = re.match( '^Python:(.*)$', mem )
                if m:
                    # python list-generating expression
                    try:
                        members += eval( m.groups()[0] )
                    except:
                        raise SuiteConfigError, 'Python error: ' + mem
                else:
                    members.append(mem)
            self['task families'][fam] = members
            self.members[ fam ] = members
            for task in self['task families'][fam]:
                self.member_of[ task ] = fam

        # Parse task config generators. If the [[TASK]] section name
        # is a family name, or a list of task names, or is a list-
        # generating Python expresion, then it is a list of task names
        # for which the subsequent config applies to each member. We
        # copy the config section for each member and substitute
        # '$(TASK)' for the actual task name in all config items.
        for item in self['tasks']:
            delete_item = True
            m = re.match( '^Python:(.*)$', item )
            if item in self['task families']:
                # a task family
                task_names = self.members[item]
                delete_item = False
            elif m:
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
                self.specialize( name, tconfig, self['tasks'][item] )
                # record it under the task name
                self['tasks'][name] = tconfig

            if delete_item:
                # delete the original multi-task section
                del self['tasks'][item]

        # NAMESPACE IMPLEMENTATION
        for task in self['tasks']:
            hier = []
            ns = task.rsplit('.',1)[0]
            if ns == task:
                ns = self['tasks'][task]['namespace']
            self.get_hierarchy( ns, hier ) # [foo, bar, global]
            hier.pop() # [foo, bar]
            hier.reverse() # [bar, foo]
            taskconf = self['namespaces']['global'].odict()
            for ns in hier:
                self.inherit( taskconf, self['namespaces'][ns] )
            self.inherit( taskconf, self['tasks'][task] )
            self['tasks'][task] = taskconf

    def get_hierarchy( self, ns, hier ):
        hier.append( ns )
        if ns == 'global' or not ns:
            return
        inherit = ns.rsplit('.',1)[0]
        if inherit == ns:
            inherit = self['namespaces'][ns]['namespace']
        self.get_hierarchy( inherit, hier )

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
                trigger = self['tasks'][task_name]['outputs'][output_name]
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
        #   (a) self['tasks'][name] 
        #       contains the task definition sections of the suite.rc file.
        #   (b) self.taskdefs[name]
        #       contains tasks that will be used, defined by the graph.
        # Tasks (a) may be defined but not used (e.g. commented out of the graph)
        # Tasks (b) may not be defined in (a), in which case they are dummied out.
        for name in self.taskdefs:
            if name not in self['tasks']:
                print >> sys.stderr, 'WARNING: task "' + name + '" is defined only by graph: it will run as a dummy task.'
        for name in self['tasks']:
            if name not in self.taskdefs:
                print >> sys.stderr, 'WARNING: task "' + name + '" is defined in [tasks] but not used in the graph.'

        # warn if listed special tasks are not defined
        for type in self['special tasks']:
            for name in self['special tasks'][type]:
                if type == 'clock-triggered':
                    name = re.sub('\(.*\)','',name)
                if re.search( '[^0-9a-zA-Z_]', name ):
                    raise SuiteConfigError, 'ERROR: Illegal ' + type + ' task name: ' + name
                if name not in self.taskdefs and name not in self['tasks']:
                    print >> sys.stderr, 'WARNING: ' + type + ' task "' + name + '" is not defined in [tasks] or used in the graph.'

        # check task insertion groups contain valid tasks
        for group in self['task insertion groups']:
            for name in self['task insertion groups'][group]:
                if name not in self['tasks'] and name not in self.taskdefs:
                    # This is not an error because it could be caused by
                    # temporary commenting out of a task in the graph,
                    # and it won't cause catastrophic failure of the
                    # insert command.
                    print >> sys.stderr, 'WARNING: task "' + name + '" of insertion group "' + group + '" is not defined.'

        # check 'tasks to exclude|include at startup' contains valid tasks
        for name in self['tasks to include at startup']:
                if name not in self['tasks'] and name not in self.taskdefs:
                    raise SuiteConfigError, "ERROR: " + name + ' in "tasks to include at startup" is not defined in [tasks] or graph.'
        for name in self['tasks to exclude at startup']:
                if name not in self['tasks'] and name not in self.taskdefs:
                    raise SuiteConfigError, "ERROR: " + name + ' in "tasks to exclude at startup" is not defined in [tasks] or graph.'

        # check graphed hours are consistent with [tasks]->[[NAME]]->hours (if defined)
        for name in self.taskdefs:
            # task 'name' is in graph
            if name in self['tasks']:
                # [tasks][name] section exists
                section_hours = [int(i) for i in self['tasks'][name]['hours'] ]
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

        # TO DO: check listed family members in the same way
        # TO DO: check that any multiple appearance of same task  in
        # 'special tasks' is valid. E.g. a task can be both
        # 'sequential' and 'clock-triggered' at the time, but not both
        # 'model' and 'sequential' at the same time.

    def process_configured_directories( self ):
        # absolute path, but can use ~user, env vars ($HOME etc.):
        self['suite log directory'] = \
                os.path.expandvars( os.path.expanduser( self['suite log directory']))
        self['state dump directory'] =  \
                os.path.expandvars( os.path.expanduser( self['state dump directory']))
        self['job submission log directory' ] = \
                os.path.expandvars( os.path.expanduser( self['namespaces']['global']['job submission log directory' ]))
        self['visualization']['run time graph']['directory'] = \
                os.path.expandvars( os.path.expanduser( self['visualization']['run time graph']['directory']))

    def create_directories( self ):
        # create logging, state, and job log directories if necessary
        for dir in [
            self['suite log directory'], 
            self['state dump directory'],
            self['job submission log directory']]: 
            mkdir_p( dir )

    def get_filename( self ):
        return self.file

    def get_dirname( self ):
        return self.dir

    def get_title( self ):
        return self['title']

    def get_description( self ):
        return self['description']

    def get_coldstart_task_list( self ):
        # TO DO: automatically determine this by parsing the dependency
        #        graph - requires some thought.
        # For now user must define this:
        return self['special tasks']['cold start']

    def get_startup_task_list( self ):
        return self['special tasks']['startup'] + self.async_oneoff_tasks + self.async_repeating_tasks

    def get_task_name_list( self ):
        # return list of task names used in the dependency diagram,
        # not the full list of defined tasks (self['tasks'].keys())
        if not self.tasks_loaded:
            self.load()
        tasknames = self.taskdefs.keys()
        tasknames.sort(key=str.lower)  # case-insensitive sort
        return tasknames

    def get_asynchronous_task_name_list( self ):
        names = []
        if not self.tasks_loaded:
            self.load()
        for tn in self.taskdefs:
            if self.taskdefs[tn].type == 'async_repeating' or self.taskdefs[tn].type == 'async_daemon' or self.taskdefs[tn].type == 'async_oneoff':
                names.append(tn)
        names.sort(key=str.lower)
        return names

    def get_full_task_name_list( self ):
        # return list of task names used in the dependency diagram,
        # and task sections (self['tasks'].keys())
        if not self.tasks_loaded:
            self.load()
        gtasknames = self.taskdefs.keys()
        stasknames = self['tasks'].keys()
        tasknames = {}
        for tn in gtasknames + stasknames:
            if tn not in tasknames:
                tasknames[tn] = True
        all_tasknames = tasknames.keys()
        all_tasknames.sort(key=str.lower)  # case-insensitive sort
        return all_tasknames

    def process_graph_line( self, line, section, graph_only=False ):
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


        # replace family names with family members
        if not graph_only or self['visualization']['show family members']:
            # TO DO: the following is overkill for just graphing.
            for fam in self['task families']:
                # fam:fail - replace with conditional expressing 
                # "at least one member failed AND all members succeeded or failed"
                # ( a:fail | b:fail ) & ( a | a:fail ) & ( b|b:fail )
                if re.search( r'\b' + fam + ':fail' + r'\b', line ):
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
                    mems = ' & '.join( self.members[fam] )
                    line = re.sub( r'\b' + fam + r'\b', mems, line )

        # split line on arrows
        tokens = re.split( '\s*(=[>x])\s*', line ) # a => b =x c
        tasks = tokens[0::2]                       # [a, b, c] 
        arrow = tokens[1::2]                       # [=>, =x]

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
           
            # parentheses are used for intercycle dependencies: (T-6) etc.

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

            suicide = False
            if arrow[i] == '=x':
                suicide = True

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

            for r in rights:
                if ttype != 'cycling':
                    for n in lnames + [r]:
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
                if graph_only:
                    self.generate_nodes_and_edges( lexpression, lnames, r, ttype, validity, suicide )
                else:
                    asyncid_pattern = None
                    if ttype == 'async_repeating':
                        m = re.match( '^ASYNCID:(.*)$', section )
                        asyncid_pattern = m.groups()[0]
                    self.generate_taskdefs( lnames, r, ttype, section, asyncid_pattern )
                    self.generate_triggers( lexpression, lnames, r, section, asyncid_pattern, suicide )
 
            # self.edges left side members can be:
            #   foo           (task name)
            #   foo:N         (specific output)
            #   foo(T-DD)     (intercycle dep)
            #   foo:N(T-DD)   (both)

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

            if name not in self.taskdefs:
                self.taskdefs[ name ] = self.get_taskdef( name )

            # TO DO: setting type should be consolidated to get_taskdef()
            if name in self.async_oneoff_tasks:
                # this catches oneoff async tasks that begin a repeating
                # async section as well.
                self.taskdefs[name].type = 'async_oneoff'
            elif ttype == 'async_repeating':
                self.taskdefs[name].asyncid_pattern = asyncid_pattern
                if name == self['dependencies'][section]['daemon']:
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
                if lnode.name in self['special tasks']['startup'] or \
                        lnode.name in self.async_oneoff_tasks:
                    self.taskdefs[right].add_startup_trigger( trigger, section )
                elif lnode.name in self.async_repeating_tasks:
                    self.taskdefs[right].loose_prerequisites.append(trigger)
                else:
                    # TO DO: ALSO CONSIDER SUICIDE FOR STARTUP AND ASYNC
                    self.taskdefs[right].add_trigger( trigger, section, suicide )
        else:
            # replace some chars for later use in regular  expressions.
            expr = re.sub( '[-\[\]:]', '_', lexpression )
            # using last lnode ...
            if lnode.name in self['special tasks']['startup'] or \
                    lnode.name in self.async_oneoff_tasks:
                self.taskdefs[right].add_startup_conditional_trigger( ctrig, expr, section )
            elif lnode.name in self.async_repeating_tasks:
                # TO DO!!!!
                raise SuiteConfigError, 'ERROR: repeating async task conditionals not done yet'
            else:
                # TO DO: ALSO CONSIDER SUICIDE FOR STARTUP AND ASYNC
                self.taskdefs[right].add_conditional_trigger( ctrig, expr, section, suicide )

    def get_graph( self, start_ctime, stop, colored=True, raw=False ):
        if not self.graph_loaded:
            self.load(graph_only=True)
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
            gr_edges.append( (left, right, False, False, False) )
	
        cycles = self.edges.keys()

        if len(cycles) != 0:
            cycles.sort(key=int)
            ctime = start_ctime
            foo = ct( ctime )

            hour = str(int(start_ctime[8:10])) # get string without zero padding
            # TO DO: TEST ZERO PADDING IN SECTION HEADINGS
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

                        if self['visualization']['show family members']:
                            # replace a family with its members
                            # and show effective dependencies
                            if lname in self.members and rname in self.members:
                                # both families
                                for lmem in self.members[lname]:
                                    for rmem in self.members[rname]:
                                        lmemid = lmem + '%' + lctime
                                        rmemid = rmem + '%' + rctime
                                        gr_edges.append( (lmemid, rmemid, False, e.suicide, e.conditional ) )
                            elif lname in self.members:
                                # left family
                                for mem in self.members[lname]:
                                    memid = mem + '%' + lctime
                                    gr_edges.append( (memid, right, False, e.suicide, e.conditional ) )
                            elif rname in self.members:
                                # right family
                                for mem in self.members[rname]:
                                    memid = mem + '%' + rctime
                                    gr_edges.append( (left, memid, False, e.suicide, e.conditional ) )
                            else:
                                # no families
                                gr_edges.append( (left, right, False, e.suicide, e.conditional ) )
                        else:
                            method = 'nonfam'
                            if lname in self.member_of and rname in self.member_of:
                                # l and r are both members of families
                                if self.member_of[lname] == self.member_of[rname]:
                                    # both members of the same family
                                    method = 'invis'
                                else:
                                    # members of different families
                                    method = 'twofam'
                            elif lname in self.member_of:
                                # l is a member of a family but r is not
                                method = 'lfam'
                            elif rname in self.member_of:
                                # r is a member of a family but l is not
                                method = 'rfam'

                            if method ==  'nonfam':
                                gr_edges.append( (left, right, False, e.suicide, e.conditional ) )
                            elif method == 'lfam':
                                gr_edges.append( (self.member_of[lname] + '%' + lctime, right, True, e.suicide, e.conditional ) )
                            elif method == 'rfam':
                                gr_edges.append( (left, self.member_of[rname] + '%' + rctime, True, e.suicide, e.conditional ) )
                            elif method == 'twofam':
                                gr_edges.append( (self.member_of[lname] + '%' + lctime, self.member_of[rname] + '%' + rctime, True, e.suicide, e.conditional ) )

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

    def prev_cycle( self, cycle, cycles ):
        i = cycles.index( cycle )
        if i == 0:
            prev = cycles[-1]
        else:
            prev = cycles[i-1]
        return prev

    def load( self, graph_only=False ):
        # parse the suite dependencies section
        for item in self['dependencies']:
            if item == 'graph':
                # One-off asynchronous tasks.
                section = "once"
                graph = self['dependencies']['graph']
                if graph == None:
                    # this means no async_oneoff tasks defined
                    continue
            else:
                section = item
                try:
                    graph = self['dependencies'][item]['graph']
                except IndexError:
                    raise SuiteConfigError, 'Missing graph string in [dependencies]['+item+']'
                #raise SuiteConfigError, 'Illegal Section: [dependencies]['+section+']'

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
                    self.process_graph_line( item, section, graph_only )

        self.graph_loaded = True
        if graph_only:
            return

        # task families
        # TO DO: IS THIS NEEDED?
        #for name in self['task families']:
        #    mems = self['task families'][name]
        #    for mem in mems:
        #        self.taskdefs[mem].member_of = name
        #        if name in self.async_oneoff_tasks:
        #            self.taskdefs[mem].type = "async_oneoff"
        #            if mem not in self.async_oneoff_tasks:
        #                self.async_oneoff_tasks.append(mem)
        #        elif name in self.async_repeating_tasks:
        #            self.taskdefs[mem].type = "async_repeating"
        #            if mem not in self.async_repeating_tasks:
        #                self.async_repeating_tasks.append(mem)

        # sort hours list for each task
        for name in self.taskdefs:
            self.taskdefs[name].hours.sort( key=int ) 

        self.load_raw_task_definitions()

        self.__check_tasks()

        self.tasks_loaded = True

    def get_taskdef( self, name, strict=False ):
        try:
            taskd = taskdef.taskdef( name )
        except taskdef.DefinitionError, x:
            raise SuiteConfigError, str(x)

        # SET ONE OFF TASK INDICATOR
        #   cold start and startup tasks are automatically one off
        if name in self['special tasks']['one off'] or \
            name in self['special tasks']['startup'] or \
            name in self['special tasks']['cold start']:
                taskd.modifiers.append( 'oneoff' )

        # SET SEQUENTIAL TASK INDICATOR
        if name in self['special tasks']['sequential']:
            taskd.modifiers.append( 'sequential' )

        # SET MODEL TASK INDICATOR
        # (TO DO - identify these tasks from the graph?)
        elif name in self['special tasks']['models with explicit restart outputs']:
            taskd.type = 'tied'
        else:
            taskd.type = 'free'

        # ONLY USING FREE TASK FOR NOW (MODELS MUST BE SEQUENTIAL)

        # SET CLOCK-TRIGGERED TASKS
        if name in self.clock_offsets:
            taskd.modifiers.append( 'clocktriggered' )
            taskd.clocktriggered_offset = self.clock_offsets[name]

        if name not in self['tasks']:
            if strict:
                raise SuiteConfigError, 'Task not defined: ' + name

            # inhabit the global namespace and carry on as usual
            taskconfig = self['namespaces']['global'].odict()
 
            if self.simulation_mode:
                taskd.job_submit_method = self['simulation mode']['job submission method']
            else:
                # global namespace job submit method
                taskd.job_submit_method = self['namespaces']['global']['job submission method']
            ##return taskd
        else:
            taskconfig = self['tasks'][name]

        taskd.description = taskconfig['description']

        for lbl in taskconfig['outputs']:
            # replace $(CYCLE_TIME) with $(TAG) in explicit outputs
            taskd.outputs.append( re.sub( 'CYCLE_TIME', 'TAG', taskconfig['outputs'][lbl] ))

        if not taskconfig['ignore task owners']:
            taskd.owner = taskconfig['owner']

        # TO DO: consolidate with just above
        if self.simulation_mode:
            taskd.job_submit_method = self['simulation mode']['job submission method']
        else:
            taskd.job_submit_method = taskconfig['job submission method']

        taskd.job_submit_log_directory = taskconfig['job submission log directory']

        if taskconfig['remote host']:
            taskd.remote_host = taskconfig['remote host']
            # consistency check
            if not taskconfig['remote cylc directory']:
                raise SuiteConfigError, name + ": tasks with a remote host must specify the remote cylc directory"

        taskd.remote_cylc_directory = taskconfig['remote cylc directory']
        taskd.remote_suite_directory = taskconfig['remote suite directory']

        taskd.manual_messaging = taskconfig['manual task completion messaging']

        # task-specific event hook scripts
        taskd.hook_scripts[ 'submitted' ]         = taskconfig['task submitted hook script']
        taskd.hook_scripts[ 'submission failed' ] = taskconfig['task submission failed hook script']
        taskd.hook_scripts[ 'started'   ]         = taskconfig['task started hook script'  ]
        taskd.hook_scripts[ 'warning'   ]         = taskconfig['task warning hook script'  ]
        taskd.hook_scripts[ 'succeeded' ]         = taskconfig['task succeeded hook script' ]
        taskd.hook_scripts[ 'failed'    ]         = taskconfig['task failed hook script'   ]
        taskd.hook_scripts[ 'timeout'   ]         = taskconfig['task timeout hook script'  ]
        # task-specific timeout hook scripts
        taskd.timeouts[ 'submission'    ]     = taskconfig['task submission timeout in minutes']
        taskd.timeouts[ 'execution'     ]     = taskconfig['task execution timeout in minutes' ]
        taskd.timeouts[ 'reset on incoming' ] = taskconfig['reset execution timeout on incoming messages']

        taskd.logfiles    = taskconfig[ 'extra log files' ]
        taskd.commands    = taskconfig[ 'command' ]
        taskd.environment = taskconfig[ 'environment' ]
        taskd.directives  = taskconfig[ 'directives' ]

        return taskd

    def get_task_proxy( self, name, ctime, state, stopctime, startup ):
        # get a proxy for a task in the dependency graph.
        if not self.tasks_loaded:
            # load all tasks defined by the graph
            self.load()
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
        hours = self['tasks'][name]['hours']
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
                print >> sys.stderr, "WARNING: no hours in graph or [tasks][["+name+"]]; task can be 'submit'ed but not inserted into the suite."
            else:
                # if 'submit'ed alone (see just above):
                print >> sys.stderr, "WARNING: " + name + ": no hours in graph or [tasks][["+name+"]]; task can be 'submit'ed but not inserted into the suite."
                print >> sys.stderr, "WARNING: " + name + ": no hours defined - task will be submitted with the exact cycle time " + ctime
            td.hours = [ chour ]
        else:
            td.hours = [ int(i) for i in hours ]
        tdclass = td.get_task_class()( ctime, 'waiting', startup, stopctime )
        return tdclass

    def get_task_class( self, name ):
        if not self.tasks_loaded:
            self.load()
        return self.taskdefs[name].get_task_class()

    def load_raw_task_definitions( self ):
        # !!!!!! DEVELOPMENT USE -EXPERTS ONLY !!!!!!
        # This method may use items defined in suite.rc:[raw task definitions]
        # to test new task proxy class developments without bothering
        # with suite.rc graph parsing. It is not guaranteed to be
        # complete, i.e. you may not be able to translate all currently 
        # graphable suites into raw form without adding to this method.

        count_raw = 0
        rawtd = self['raw task definitions']
        for name in rawtd:
            count_raw += 1
            taskconfig = rawtd[name]
            try:
                taskd = taskdef.taskdef( name )
            except taskdef.DefinitionError, x:
                raise SuiteConfigError, str(x)

            taskd.type = taskconfig['type']

            for mod in taskconfig['type modifiers']:
                taskd.modifiers.append(mod)
                if mod == 'clocktriggered':
                    taskd.clocktriggered_offset = taskconfig['clock trigger offset in hours']

            for lbl in taskconfig['outputs']:
                taskd.outputs.append( taskconfig['outputs'][lbl] )

            if not self['ignore task owners']:
                taskd.owner = taskconfig['owner']

            if self.simulation_mode:
                # use simulation mode specific job submit method for all tasks
                taskd.job_submit_method = self['simulation mode']['job submission method']
            elif taskconfig['job submission method'] != None:
                # a task-specific job submit method was specified
                taskd.job_submit_method = taskconfig['job submission method']
            else:
                # suite default job submit method
                taskd.job_submit_method = self['job submission method']

            taskd.job_submit_log_directory = taskconfig['job submission log directory']

            if taskconfig['remote host']:
                taskd.remote_host = taskconfig['remote host']
                # consistency check
                if not taskconfig['remote cylc directory']:
                    raise SuiteConfigError, name + ": tasks with a remote host must specify the remote cylc directory"

            taskd.remote_cylc_directory = taskconfig['remote cylc directory']
            taskd.remote_suite_directory = taskconfig['remote suite directory']
            taskd.manual_messaging = taskconfig['manual task completion messaging']

            taskd.hook_scripts[ 'submitted' ]         = taskconfig['task submitted hook script']
            taskd.hook_scripts[ 'submission failed' ] = taskconfig['task submission failed hook script']
            taskd.hook_scripts[ 'started'   ]         = taskconfig['task started hook script'  ]
            taskd.hook_scripts[ 'warning'   ]         = taskconfig['task warning hook script'  ]
            taskd.hook_scripts[ 'succeeded' ]         = taskconfig['task succeeded hook script' ]
            taskd.hook_scripts[ 'failed'    ]         = taskconfig['task failed hook script'   ]
            taskd.hook_scripts[ 'timeout'   ]         = taskconfig['task timeout hook script'  ]
            # task-specific timeout hook scripts
            taskd.timeouts[ 'submission'    ]     = taskconfig['task submission timeout in minutes']
            taskd.timeouts[ 'execution'     ]     = taskconfig['task execution timeout in minutes' ]
            taskd.timeouts[ 'reset on incoming' ] = taskconfig['reset execution timeout on incoming messages']

            taskd.description = taskconfig['description']
            taskd.commands = taskconfig['command']
            taskd.logfiles = taskconfig['extra log files']
            taskd.envrionment = taskconfig['environment']
            taskd.directives = taskconfig['directives']

            valid_hours = taskconfig['hours string']
            if valid_hours:
                # cycling tasks
                taskd.set_valid_hours( valid_hours )
                for lbl in taskconfig['prerequisites']:
                    taskd.add_trigger( taskconfig['prerequisites'][lbl], valid_hours )
            elif taskconfig['asyncid pattern']:
                # repeating asynchronous tasks
                taskd.asyncid_pattern = taskconfig['asyncid pattern']
                lpre = taskconfig['prerequisites']
                for lbl in lpre:
                    pre = re.sub( '\$\(ASYNCID\)', '(' + taskconfig['asyncid pattern'] + ')', lpre[lbl] )
                    taskd.loose_prerequisites.append(pre)
            else:
                # one-off asynchronous tasks
                for lbl in taskconfig['prerequisites']:
                    taskd.add_asynchronous_trigger( taskconfig['prerequisites'][lbl] )

            if taskconfig['startup prerequisites']:
                for lbl in taskconfig['startup prerequisites']:
                    taskd.add_startup_trigger( taskconfig['startup prerequisites'][lbl], valid_hours )
 
            self.taskdefs[name] = taskd

        if count_raw != 0:
            print >> sys.stderr, "WARNING: this suite contains " + str(count_raw) + " raw (non-graphed) task definitions."
 
