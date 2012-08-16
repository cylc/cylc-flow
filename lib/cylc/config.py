#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

# TO DO: document use foo[T-6]:out1, not foo:out1 with
# <CYLC_TASK_CYCLE_TIME-6> in the output message.

# NOTE: configobj.reload() apparently does not revalidate (list-forcing
# is not done, for example, on single value lists with no trailing
# comma) ... so to reparse the file  we have to instantiate a new config
# object.

import taskdef
from copy import deepcopy
from collections import deque
from OrderedDict import OrderedDict
from cycle_time import ct, CycleTimeError
import re, os, sys, logging
from mkdir_p import mkdir_p
from validate import Validator
from configobj import get_extra_values, flatten_errors, Section
from cylcconfigobj import CylcConfigObj, ConfigObjError
from graphnode import graphnode, GraphNodeError
from print_tree import print_tree
from prerequisites.conditionals import TriggerExpressionError
from regpath import RegPath
from trigger import triggerx
from output import outputx
from TaskID import TaskID, AsyncTag
from Jinja2Support import Jinja2Process, TemplateError, TemplateSyntaxError
from continuation_lines import join
from include_files import inline

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

class TaskNotDefinedError( SuiteConfigError ):
    pass

class edge( object):
    def __init__( self, l, r, cyclr, sasl=False, suicide=False, conditional=False ):
        """contains qualified node names, e.g. 'foo[T-6]:out1'"""
        self.left = l
        self.right = r
        self.cyclr = cyclr
        self.sasl = sasl
        self.suicide = suicide
        self.conditional = conditional

    def get_right( self, intag, not_first_cycle, raw, startup_only, exclude ):
        tag = str(intag)
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

        return TaskID( self.right, tag )

    def get_left( self, intag, not_first_cycle, raw, startup_only, exclude ):
        tag = str(intag)
        # (exclude was briefly used - April 2011 - to stop plotting temporary tasks)
        if self.left in exclude:
            return None

        first_cycle = not not_first_cycle

        # strip off special outputs
        left = re.sub( ':\w+', '', self.left )

        if re.search( '\[\s*T\s*-\d+\s*\]', left ) and first_cycle:
            # ignore intercycle deps in first cycle
            return None

        if left in startup_only:
            if not first_cycle or raw:
                return None

        if self.sasl:
            # left node is asynchronous, so override the cycler
            tag = '1'
        else:
            m = re.search( '(\w+)\s*\[\s*T\s*([+-])(\d+)\s*\]', left )
            if m: 
                left, sign, offset = m.groups()
                tag = self.cyclr.__class__.offset( tag, offset )
            else:
                tag = tag

        return TaskID( left, tag )

class config( CylcConfigObj ):

    def __init__( self, suite, suiterc, owner=None, 
            simulation_mode=False, verbose=False, 
            validation=False, pyro_timeout=None, collapsed=[] ):
        self.simulation_mode = simulation_mode
        self.verbose = verbose
        if pyro_timeout:
            self.pyro_timeout = float(pyro_timeout)
        else:
            self.pyro_timeout = None
        self.edges = []
        self.cyclers = []
        self.taskdefs = OrderedDict()
        self.validation = validation

        self.async_oneoff_edges = []
        self.async_oneoff_tasks = []
        self.async_repeating_edges = []
        self.async_repeating_tasks = []
        self.cycling_tasks = []
        self.tasks_by_cycler = {}

        self.family_hierarchy = {}
        self.families_used_in_graph = []

        self.suite = suite
        self.file = suiterc
        self.dir = os.path.dirname(suiterc)

        self.owner = owner
        if owner:
            self.homedir = os.path.expanduser( '~' + owner )
        else:
            self.homedir = os.environ[ 'HOME' ]

        if not os.path.isfile( self.file ):
            raise SuiteConfigError, 'File not found: ' + self.file

        self.spec = os.path.join( os.environ[ 'CYLC_DIR' ], 'conf', 'suiterc.spec')

        if self.verbose:
            print "Loading suite.rc"

        f = open( self.file )
        flines = f.readlines()
        f.close()

        # handle cylc include-files
        flines = inline( flines, self.dir )

        # handle Jinja2 expressions
        try:
            suiterc = Jinja2Process( flines, self.dir, self.verbose )
        except TemplateSyntaxError, x:
            lineno = x.lineno + 1  # (flines array starts from 0)
            print >> sys.stderr, 'Jinja2 Template Syntax Error, line', lineno
            print >> sys.stderr, flines[x.lineno]
            raise SystemExit(str(x))
        except TemplateError, x:
            print >> sys.stderr, 'Jinja2 Template Error'
            raise SystemExit(x)

        # handle cylc continuation lines
        suiterc = join( suiterc )

        try:
            CylcConfigObj.__init__( self, suiterc, configspec=self.spec )
        except ConfigObjError, x:
            raise SuiteConfigError, x

        if self.verbose:
            print "Validating against the suite.rc spec"
        # validate and convert to correct types
        val = Validator()
        test = self.validate( val, preserve_errors=True )
        if test != True:
            # Validation failed
            failed_items = flatten_errors( self, test )
            # Always print reason for validation failure
            for item in failed_items:
                sections, key, result = item
                print >> sys.stderr, ' ',
                for sec in sections:
                    print >> sys.stderr, sec, '->',
                print >> sys.stderr, key
                if result == False:
                    print >> sys.stderr, "Required item missing."
                else:
                    print >> sys.stderr, result
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

        if self.verbose:
            print "Parsing clock-triggered tasks"
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
            print "Parsing runtime name lists"
        # If a runtime section heading is a list of names then the
        # subsequent config applies to each member. 
        for item in self['runtime']:
            if re.search( ',', item ):
                # list of task names
                # remove trailing commas and spaces
                tmp = item.rstrip(', ')
                task_names = re.split(', *', tmp )
            else:
                # a single task name 
                continue
            # generate task configuration for each list member
            for name in task_names:
                # create a new task config section
                tconfig = OrderedDict()
                # replicate the actual task config
                self.replicate( name, tconfig, self['runtime'][item] )
                # record it under the task name
                self['runtime'][name] = tconfig

            # delete the original multi-task section
            del self['runtime'][item]

        self.members = {}
        if self.verbose:
            print "Parsing the runtime namespace hierarchy"

        # RUNTIME INHERITANCE
        for label in self['runtime']:
            hierarchy = []
            name = label
            self.interpolate( name, self['runtime'][name], '<NAMESPACE>' )
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

        collapsed_rc = self['visualization']['collapsed families']
        if len( collapsed ) > 0:
            # this overrides the rc file item
            self.closed_families = collapsed
        else:
            self.closed_families = collapsed_rc
        for cfam in self.closed_families:
            if cfam not in self.members:
                print >> sys.stderr, 'WARNING, [visualization][collapsed families]: ignoring ' + cfam + ' (not a family)'
                self.closed_families.remove( cfam )
        self.vis_families = list(self.closed_families)

        if not self.pyro_timeout:
            # no timeout specified on the command line
            tmp = self['cylc']['pyro connection timeout']
            if tmp:
                self.pyro_timeout = float(tmp)

        if self.verbose:
            print "Pyro connection timeout for tasks in this suite:", self.pyro_timeout, "seconds"

        if self.verbose:
            print "Checking suite event hooks"
        script = None
        events = []
        if not self.simulation_mode or self['cylc']['simulation mode']['event hooks']['enable']:
            # configure suite event hooks
            script = self['cylc']['event hooks']['script']
            events = self['cylc']['event hooks']['events']
            for event in events:
                if event not in ['shutdown']:
                    raise SuiteConfigError, "ERROR, illegal suite hook event: " + event
        if len(events) == 0 and script:
            # this is not a fatal error
            print >> sys.stderr, "WARNING: suite event handler specified without events to handle."
        if len(events) > 0 and not script:
            # but this is
            raise SuiteConfigError, "ERROR, no handler specified for these suite events: " + ','.join(events)

        self.process_directories()

        if self.verbose:
            print 'Parsing the dependency graph'
        self.graph_found = False
        self.load_graph()
        if not self.graph_found:
            raise SuiteConfigError, 'No suite dependency graph defined.'

        # Compute runahead limit
        # 1/ take the largest of the minimum limits from each graph section
        if len(self.cyclers) != 0:
            # runahead limit is only relevant for cycling sections
            mrls = []
            mrl = None
            for cyc in self.cyclers:
                mrls.append(cyc.get_def_min_runahead())
            mrl = max(mrls)
            if self.verbose:
                print "Largest minimum runahead limit from cycling modules:", mrl, "hours"
            # Add one hour, which is enough to prevent single-cycle intercycle
            # dependence from stalling the suite. To Do: find a robust
            # method to handle any kind of intercycle dependence (is it
            # ever more than one cycle in practice?)
            mrl += 1

            # 2/ or if there is a configured runahead limit, use it.
            rl = self['scheduling']['runahead limit']
            if rl:
                if self.verbose:
                    print "Configured runahead limit: ", rl, "hours"
                if rl < mrl:
                    print >> sys.stderr, 'WARNING: runahead limit (' + str(rl) + ') may be too low (<' + str(mrl) + ')'
                crl = rl
            else:
                crl = mrl
                if self.verbose:
                    print "Runahead limit defaulting to:", crl, "hours"

            self['scheduling']['runahead limit'] = crl

        self.family_tree = {}
        self.task_runtimes = {}
        self.define_inheritance_tree( self.family_tree, self.family_hierarchy )
        self.prune_inheritance_tree( self.family_tree, self.task_runtimes )

        self.process_queues()
        if self.validation:
            self.check_tasks()

        # Default visualization start and stop cycles (defined here
        # rather than in the spec file so we can set a sensible stop
        # time if only the start time is specified by the user).
        vizfinal = False
        vizstart = False
        if self['visualization']['initial cycle time']:
            vizstart = True
        if self['visualization']['final cycle time']:
            vizfinal = True

        if vizstart and vizfinal:
            pass
        elif vizstart:
            self['visualization']['final cycle time'] = self['visualization']['initial cycle time']
        elif vizfinal:
            self['visualization']['initial cycle time'] = self['visualization']['final cycle time']
        else:
            self['visualization']['initial cycle time'] = 2999010100
            self['visualization']['final cycle time'] = 2999010123

        # Define family node groups automatically so that family and
        # member nodes can be styled together using the family name.
        # Users can override this for individual nodes or sub-groups.
        ng = self['visualization']['node groups']
        for fam in self.members:
            if fam not in ng:
                ng[fam] = [fam] + self.members[fam]
        # (Note that we're retaining 'default node attributes' even
        # though this could now be achieved by styling the root family,
        # because putting default attributes for root in suiterc.spec
        # results in root appearing last in the ordered dict of node
        # names, so it overrides the styling for lesser groups and
        # nodes, whereas the reverse is needed - fixing this would
        # require reordering task_attr in lib/cylc/graphing.py).

    def adopt_orphans( self, orphans ):
        # Called by the scheduler after reloading the suite definition
        # at run time and finding any live task proxies whose
        # definitions have been removed from the suite. Keep them 
        # in the default queue and under the root family, until they
        # run their course and disappear.
        queues = self['scheduling']['queues']
        for orphan in orphans:
            self.family_hierarchy[orphan] = [ orphan, 'root' ]
            queues['default']['members'].append( orphan )

    def process_queues( self ):
        # TO DO: user input consistency checking (e.g. duplicate queue
        # assignments and non-existent task names)

        # NOTE: this method modifies the parsed config dict itself.

        queues = self['scheduling']['queues']
        # add all tasks to the default queue
        queues['default']['members'] = self.get_task_name_list()
        #print 'INITIAL default', queues['default']['members']
        for queue in queues:
            if queue == 'default':
                continue
            # remove assigned tasks from the default queue
            qmembers = []
            for qmember in queues[queue]['members']:
                if qmember in self.members:
                    # qmember is a family: replace with family members
                    for fmem in self.members[qmember]:
                        qmembers.append( fmem )
                        queues['default']['members'].remove( fmem )
                else:
                    # qmember is a task
                    qmembers.append(qmember)
                    queues['default']['members'].remove( qmember )
            queues[queue]['members'] = qmembers
        #for queue in queues:
        #    print queue, queues[queue]['members']

    def get_inheritance( self ):
        inherit = {}
        for ns in self['runtime']:
            #if 'inherit' in self['runtime'][ns]:
            parent = self['runtime'][ns]['inherit']
            if ns != "root" and not parent:
                parent = "root"
            inherit[ns] = parent
        return inherit

    def define_inheritance_tree( self, tree, hierarchy ):
        # combine inheritance hierarchies into a tree structure.
        for rt in hierarchy:
            hier = deepcopy(hierarchy[rt])
            hier.reverse()
            foo = tree
            for item in hier:
                if item not in foo:
                    foo[item] = {}
                foo = foo[item]

    def prune_inheritance_tree( self, tree, runtimes ):
        # When self.family_tree is constructed leaves are {}. This
        # replaces the leaves with first line of task description, and
        # populates self.task_runtimes with just the leaves (tasks).
        for item in tree:
            skeys = tree[item].keys() 
            if len( skeys ) > 0:
                self.prune_inheritance_tree(tree[item], runtimes)
            else:
                description = self['runtime'][item]['description']
                dlines = re.split( '\n', description )
                dline1 = dlines[0]
                if len(dlines) > 1:
                    dline1 += '...'
                tree[item] = dline1
                runtimes[item] = self['runtime'][item]

    def print_task_list( self, filter=None, labels=None, pretty=False ):
        # determine padding for alignment of task descriptions
        tasks = self.task_runtimes.keys()
        maxlen = 0
        for task in tasks:
            if len(task) > maxlen:
                maxlen = len(task)
        padding = (maxlen+1) * ' '

        for task in tasks:
            if filter:
                if not re.search( filter, task ):
                    continue
            # print first line of task description
            description = self['runtime'][task]['description']
            dlines = re.split( '\n', description )
            dline1 = dlines[0]
            if len(dlines) > 1:
                dline1 += '...'
            print task + padding[ len(task): ] + dline1

    def print_inheritance_tree( self, filter=None, labels=None, pretty=False ):
        # determine padding for alignment of task descriptions
        if filter:
            trt = {}
            ft = {}
            fh = {}
            for item in self.family_hierarchy:
                if item not in self.task_runtimes:
                    continue
                if not re.search( filter, item ):
                    continue
                fh[item] = self.family_hierarchy[item]
            self.define_inheritance_tree( ft, fh )
            self.prune_inheritance_tree( ft, trt )
        else:
            fh = self.family_hierarchy
            ft = self.family_tree

        maxlen = 0
        for rt in fh:
            items = deepcopy(fh[rt])
            items.reverse()
            for i in range(0,len(items)):
                tmp = 2*i + 1 + len(items[i])
                if i == 0:
                    tmp -= 1
                if tmp > maxlen:
                    maxlen = tmp
        padding = (maxlen+1) * ' '
        print_tree( ft, padding=padding, unicode=pretty, labels=labels )

    def expandvars( self, item ):
        # first replace '$HOME' with actual home dir
        item = item.replace( '$HOME', self.homedir )
        # now expand any other environment variable or tilde-username
        item = os.path.expandvars( os.path.expanduser( item ))
        return item

    def process_directories(self):
        # Environment variable interpolation in directory paths.
        # Allow use of suite, BUT NOT TASK, identity variables.
        for item in self['runtime']:
            logd = self['runtime'][item]['log directory']
            if logd.find( '$CYLC_TASK_' ) != -1:
                print >> sys.stderr, 'runtime -> log directory =', logd
                raise SuiteConfigError, 'ERROR: log directories cannot be task-specific'

        os.environ['CYLC_SUITE_REG_NAME'] = self.suite
        os.environ['CYLC_SUITE_REG_PATH'] = RegPath( self.suite ).get_fpath()
        os.environ['CYLC_SUITE_DEF_PATH'] = self.dir
        self['cylc']['logging']['directory'] = \
                self.expandvars( self['cylc']['logging']['directory'])
        self['cylc']['state dumps']['directory'] =  \
                self.expandvars( self['cylc']['state dumps']['directory'])
        self['visualization']['run time graph']['directory'] = \
                self.expandvars( self['visualization']['run time graph']['directory'])

        for item in self['runtime']:
            # Local job sub log directories: interpolate all environment variables.
            self['runtime'][item]['log directory'] = self.expandvars( self['runtime'][item]['log directory'])
            # Remote log directories: just suite identity - local variables aren't relevant.
            if self['runtime'][item]['remote']['log directory']:
                for var in ['CYLC_SUITE_REG_PATH', 'CYLC_SUITE_DEF_PATH', 'CYLC_SUITE_REG_NAME']: 
                    self['runtime'][item]['remote']['log directory'] = re.sub( '\${'+var+'}'+r'\b', os.environ[var], self['runtime'][item]['remote']['log directory'])
                    self['runtime'][item]['remote']['log directory'] = re.sub( '\$'+var+r'\b',      os.environ[var], self['runtime'][item]['remote']['log directory'])

    def inherit( self, target, source ):
        for item in source:
            if isinstance( source[item], Section ):
                # recurse into nested section
                self.inherit( target[item], source[item] )
            elif source[item] != None and source[item] != []:
                # override if source is not None or an empty list
                # (don't use 'if source[item]:' because of boolean values)
                target[item] = deepcopy(source[item])  # deepcopy for list values
            else:
                pass

    def replicate( self, name, target, source ):
        # recursively replicate a generator task config section
        for item in source:
            if isinstance( source[item], Section ):
                # recursive call for to handle a sub-section
                if item not in target:
                    target[item] = OrderedDict()
                self.replicate( name, target[item], source[item] )
            else:
                target[item] = source[item]

    def interpolate( self, name, source, pattern ):
        # replace pattern with name in all items in the source tree
        for item in source:
            if isinstance( source[item], str ):
                # single source item
                source[item] = re.sub( pattern, name, source[item] )
            elif isinstance( source[item], list ):
                # a list of values 
                newlist = []
                for mem in source[item]:
                    if isinstance( mem, str ):
                        newlist.append( re.sub( pattern, name, mem ))
                    else:
                        newlist.append( mem )
                source[item] = newlist
            elif isinstance( source[item], Section ):
                # recursive call for to handle a sub-section
                self.interpolate( name, source[item], pattern )
            else:
                # boolean or None values
                continue

    def set_trigger( self, task_name, right, output_name=None, offset=None, asyncid_pattern=None, suicide=False ):
        trig = triggerx(task_name)
        trig.set_suicide(suicide)
        if output_name:
            try:
                # check for internal outputs
                trig.set_special( self['runtime'][task_name]['outputs'][output_name] )
            except KeyError:
                # There is no matching output defined under the task runtime section 
                if output_name == 'fail':
                    # OK, task:fail
                    trig.set_type('failed' )
                elif output_name == 'start':
                    # OK, task:start
                    trig.set_type('started')
                else:
                    # ERROR
                    raise SuiteConfigError, "ERROR: '" + task_name + "' does not define output '" + output_name  + "'"
            else:
                # There is a matching output defined under the task runtime section
                if self.simulation_mode:
                    # Ignore internal outputs: dummy tasks will not report them finished.
                    return None
        else:
            # default: task succeeded
            trig.set_type( 'succeeded' )

        if offset:
            trig.set_offset(offset)
             
        if task_name in self.async_oneoff_tasks:
            trig.set_async_oneoff()
        elif task_name in self.async_repeating_tasks:
            trig.set_async_repeating( asyncid_pattern)
            if trig.suicide:
                raise SuiteConfigError, "ERROR, '" + task_name + "': suicide triggers not implemented for repeating async tasks"
            if trig.type:
                raise SuiteConfigError, "ERROR, '" + task_name + "': '" + trig.type + "' triggers not implemented for repeating async tasks"
        elif task_name in self.cycling_tasks:
            trig.set_cycling()
 
        if right in self.cycling_tasks and \
            (task_name in self['scheduling']['special tasks']['start-up'] or \
                 task_name in self.async_oneoff_tasks ):
                # cycling tasks only depend on these tasks at startup
                trig.set_startup()

        return trig

    def check_tasks( self ):
        # Call after all tasks are defined.
        # ONLY IF VALIDATING THE SUITE
        # because checking conditional triggers below may be slow for
        # huge suites (several thousand tasks).
        # Note: 
        #   (a) self['runtime'][name] 
        #       contains the task definition sections of the suite.rc file.
        #   (b) self.taskdefs[name]
        #       contains tasks that will be used, defined by the graph.
        # Tasks (a) may be defined but not used (e.g. commented out of the graph)
        # Tasks (b) may not be defined in (a), in which case they are dummied out.

        if self.verbose:
            for name in self['runtime']:
                if name not in self.taskdefs:
                    if name not in self.members:
                        # any family triggers have have been replaced with members by now.
                        print >> sys.stderr, 'WARNING: task "' + name + '" is not used in the graph.'

        self.check_for_case_errors()

        # warn if listed special tasks are not defined
        for type in self['scheduling']['special tasks']:
            for name in self['scheduling']['special tasks'][type]:
                if type == 'clock-triggered':
                    name = re.sub('\(.*\)','',name)
                if re.search( '[^0-9a-zA-Z_]', name ):
                    raise SuiteConfigError, 'ERROR: Illegal ' + type + ' task name: ' + name
                if name not in self.taskdefs and name not in self['runtime']:
                    raise SuiteConfigError, 'ERROR: special task "' + name + '" is not defined.' 

        try:
            import Pyro.constants
        except:
            print >> sys.stderr, "WARNING, INCOMPLETE VALIDATION: Pyro is not installed"
            return

        # Instantiate tasks and force evaluation of conditional trigger expressions.
        if self.verbose:
            print "Checking conditional trigger expressions"
        for cyclr in self.tasks_by_cycler:
            # for each graph section
            for name in self.tasks_by_cycler[cyclr]:
                # instantiate one of each task appearing in this section
                type = self.taskdefs[name].type
                if type != 'async_repeating' and type != 'async_daemon' and type != 'async_oneoff':
                    tag = cyclr.initial_adjust_up( '2999010100' )
                else:
                    tag = '1'
                try:
                    # instantiate a task
                    # startup True here or oneoff async tasks will be ignored:
                    itask = self.taskdefs[name].get_task_class()( tag, 'waiting', None, True )
                except TypeError, x:
                    raise
                    # This should not happen as we now explicitly catch use
                    # of synchronous special tasks in an asynchronous graph.
                    # But in principle a clash of multiply inherited base
                    # classes due to choice of "special task" modifiers
                    # could cause a TypeError.
                    print >> sys.stderr, x
                    raise SuiteConfigError, '(inconsistent use of special tasks?)' 
                except Exception, x:
                    print >> sys.stderr, x
                    raise SuiteConfigError, 'ERROR, failed to instantiate task ' + str(name)
                # force trigger evaluation now
                try:
                    itask.prerequisites.eval_all()
                except TriggerExpressionError, x:
                    print >> sys.stderr, x
                    raise SuiteConfigError, "ERROR, " + name + ": invalid trigger expression."
                except Exception, x:
                    print >> sys.stderr, x
                    raise SuiteConfigError, 'ERROR, ' + name + ': failed to evaluate triggers.'
                tag = itask.next_tag()
            #print "OK:", itask.id

        # TASK INSERTION GROUPS DISABLED - WILL USE RUNTIME GROUPS FOR INSERTION ETC.
        ### check task insertion groups contain valid tasks
        ##for group in self['task insertion groups']:
        ##    for name in self['task insertion groups'][group]:
        ##        if name not in self['runtime'] and name not in self.taskdefs:
        ##            # This is not an error because it could be caused by
        ##            # temporary commenting out of a task in the graph,
        ##            # and it won't cause catastrophic failure of the
        ##            # insert command.
        ##            print >> sys.stderr, 'WARNING: task "' + name + '" of insertion group "' + group + '" is not defined.'

        # TO DO: check that any multiple appearance of same task  in
        # 'special tasks' is valid. E.g. a task can be both
        # 'sequential' and 'clock-triggered' at the time, but not both
        # 'model' and 'sequential' at the same time.

    def check_for_case_errors( self ):
        # check for case errors in task names
        # To Do: this could probably be done more efficiently!
        all_names_dict = {}
        for name in self.taskdefs.keys() + self['runtime'].keys():
            # remove legitimate duplicates (names in graph and runtime)
            if name not in all_names_dict:
                all_names_dict[name] = True
        all_names = all_names_dict.keys()
        knob = {}
        duplicates = []
        for name in [ foo.lower() for foo in all_names ]:
            if name not in knob:
                knob[name] = True
            else:
                duplicates.append(name)
        duplist = {}
        for dup in duplicates:
            for name in all_names:
                if name.lower() == dup:
                    if dup not in duplist:
                        duplist[dup] = [name]
                    else:
                        duplist[dup].append(name)
        if self.verbose:
            if len( duplist.keys() ) > 0:
                print >> sys.stderr, 'WARNING: THE FOLLOWING TASK NAMES DIFFER ONLY BY CASE:'
            for name in duplist:
                # this is probably, but not necessarily, an error.
                print >> sys.stderr, ' ', 
                for n in duplist[name]:
                    print >> sys.stderr, n,
                print >> sys.stderr, ''
 
    def create_directories( self, task=None ):
        # Create suite log, state, and local job log directories.
        dirs = [ self['cylc']['logging']['directory'], self['cylc']['state dumps']['directory'] ]
        for item in self['runtime']:
            d = self['runtime'][item]['log directory']
            if d not in dirs:
                dirs.append(d)
        for d in dirs:
            try:
                mkdir_p( d )
            except Exception, x:
                print >> sys.stderr, x
                raise SuiteConfigError, 'ERROR, illegal dir? ' + d
        
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
        # return a list of all tasks used in the dependency graph
        tasknames = self.taskdefs.keys()
        return tasknames

    def get_asynchronous_task_name_list( self ):
        names = []
        for tn in self.taskdefs:
            if self.taskdefs[tn].type == 'async_repeating' or \
                    self.taskdefs[tn].type == 'async_daemon' or \
                    self.taskdefs[tn].type == 'async_oneoff':
                names.append(tn)
        return names

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

        orig_line = line

        # [list of valid hours], or ["once"], or ["ASYNCID:pattern"]

        if section == "once":
            ttype = 'async_oneoff'
            modname = 'async'
            args = []
        elif re.match( '^ASYNCID:', section ):
            ttype = 'async_repeating'
            modname = 'async'
            args = []
        else:
            ttype = 'cycling'
            # match cycler, e.g. "Yearly( 2010, 2 )"
            m = re.match( '^(\w+)\(([\s\w,]*)\)$', section )
            if m:
                modname, cycargs = m.groups()
                # remove leading and trailing space
                cycargs = cycargs.strip()
                arglist = re.sub( '\s+$', '', cycargs )
                # split on comma with optional space each side
                args = re.split( '\s*,\s*', arglist )
            else:
                modname = self['scheduling']['cycling']
                args = re.split( ',\s*', section )

        mod = __import__( 'cylc.cycling.' + modname, globals(), locals(), [modname] )
        cyclr = getattr( mod, modname )(*args)
        self.cyclers.append(cyclr)

        ## SYNONYMS FOR TRIGGER-TYPES, e.g. 'fail' = 'failure' = 'failed'
        ## we can replace synonyms here with the standard type designator:
        # line = re.sub( r':succe(ss|ed|eded){0,1}\b', '', line )
        # line = re.sub( r':fail(ed|ure){0,1}\b', ':fail', line )
        # line = re.sub( r':start(ed){0,1}\b', ':start', line )
        # Replace "foo:finish(ed)" or "foo:complete(ed)" with "( foo | foo:fail )"
        # line = re.sub(  r'\b(\w+(\[.*?]){0,1}):(complete(d){0,1}|finish(ed){0,1})\b', r'( \1 | \1:fail )', line )

        # Replace "foo:finish" with "( foo | foo:fail )"
        line = re.sub(  r'\b(\w+(\[.*?]){0,1}):finish\b', r'( \1 | \1:fail )', line )

        # REPLACE FAMILY NAMES WITH MEMBER DEPENDENCIES
        for fam in self.members:
            # Note, in the regular expressions below, the word boundary
            # marker before the time offset pattern is required to close
            # the match in the no-offset case (offset and no-offset
            # cases are being matched by the same regular expression).

            # The replacements below all handle optional [T-n] cycle offsets.

            # 1/ Replace "fam:fail" with "(one or more members failed)
            # AND (all members either succeeded or failed)", i.e.:
            # ( a:fail | b:fail ) & ( a | a:fail ) & ( b|b:fail ).
            m = re.findall( r"\b" + fam + r"\b(\[.*?]){0,1}:fail", line )
            m.sort() # put empty offset '' first ...
            m.reverse() # ... then last
            for foffset in m:
                if fam not in self.families_used_in_graph:
                    self.families_used_in_graph.append(fam)
                mem0 = self.members[fam][0]
                cond1 = mem0 + foffset + ':fail'
                cond2 = '( ' + mem0 + foffset + ' | ' + mem0 + foffset + ':fail )' 
                for mem in self.members[fam][1:]:
                    cond1 += ' | ' + mem + foffset + ':fail'
                    cond2 += ' & ( ' + mem + foffset + ' | ' + mem + foffset + ':fail )'
                cond = '( ' + cond1 + ') & ' + cond2 
                line = re.sub( r"\b" + fam + r"\b" + re.escape(foffset) + r":fail\b", cond, line )

            # 2/ Replace "fam:start" with "mem1:start | mem2:start" etc.
            # i.e. one or more members started.
            m = re.findall( r"\b" + fam + r"\b(\[.*?]){0,1}:start", line )
            m.sort() # put empty offset '' first ...
            m.reverse() # ... then last
            for foffset in m:
                if fam not in self.families_used_in_graph:
                    self.families_used_in_graph.append(fam)
                mems = ' | '.join( [ i + foffset + ':start' for i in self.members[fam] ] )
                line = re.sub( r"\b" + fam + r"\b" + re.escape( foffset) + ':start', mems, line )

            # 3/ Replace "fam" with "mem1 & mem2" etc.
            # i.e. all members succeeded (or all members trigger off)
            m = re.findall( r"\b" + fam + r"\b(\[.*?]){0,1}", line )
            m.sort() # put empty offset '' first ...
            m.reverse() # ... then last
            for foffset in m:
                if fam not in self.families_used_in_graph:
                    self.families_used_in_graph.append(fam)
                mems = ' & '.join( [ i + foffset for i in self.members[fam] ] )
                line = re.sub( r"\b" + fam + r"\b" + re.escape( foffset), mems, line )

        # Split line on dependency arrows.
        tasks = re.split( '\s*=>\s*', line )
        # NOTE:  we currently use only one kind of arrow, but to use
        # several kinds we can split the string like this:
        #     tokens = re.split( '\s*(=[>x])\s*', line ) # a => b =x c
        #     tasks = tokens[0::2]                       # [a, b, c] 
        #     arrow = tokens[1::2]                       # [=>, =x]

        # Check for missing task names, e.g. '=> a => => b =>; this
        # results in empty or blank strings in the list of task names.
        arrowerr = False
        for task in tasks:
            if re.match( '^\s*$', task ):
                arrowerr = True
                break
        if arrowerr:
            print >> sys.stderr, orig_line
            raise SuiteConfigError, "ERROR: missing task name in graph line?"

        # get list of pairs
        for i in [0] + range( 1, len(tasks)-1 ):
            lexpression = tasks[i]

            if len(tasks) == 1:
                # single node: no rhs group
                rgroup = None
                if re.search( '\|', lexpression ):
                    print >> sys.stderr, orig_line
                    raise SuiteConfigError, "ERROR: Lone node groups cannot contain OR conditionals: " + lexpression
            else:
                rgroup = tasks[i+1]
           
            if rgroup:
                # '|' (OR) is not allowed on the right side
                if re.search( '\|', rgroup ):
                    print >> sys.stderr, orig_line
                    raise SuiteConfigError, "ERROR: OR '|' is not legal on the right side of dependencies: " + rgroup

                # (T+/-N) offsets not allowed on the right side (as yet)
                if re.search( '\[\s*T\s*[+-]\s*\d+\s*\]', rgroup ):
                    print >> sys.stderr, orig_line
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

            if section == 'once':
                # Consistency check: synchronous special tasks are
                # not allowed in asynchronous graph sections.
                spec = self['scheduling']['special tasks']
                bad = []
                for name in lnames + rights:
                    if name in spec['start-up'] or name in spec['cold-start'] or \
                            name in spec['sequential'] or name in spec['one-off']:
                                bad.append(name)
                if len(bad) > 0:
                    print >> sys.stderr, orig_line
                    print >> sys.stderr, 'ERROR, synchronous special tasks cannot be used in an asynchronous graph:'
                    print >> sys.stderr, ' ', ', '.join(bad)
                    raise SuiteConfigError, 'ERROR: inconsistent use of special tasks.'

            for rt in rights:
                # foo => '!bar' means task bar should suicide if foo succeeds.
                suicide = False
                if rt and rt.startswith('!'):
                    r = rt[1:]
                    suicide = True
                else:
                    r = rt

                asyncid_pattern = None
                if ttype != 'cycling':
                    for n in lnames + [r]:
                        if not n:
                            continue
                        try:
                            name = graphnode( n ).name
                        except GraphNodeError, x:
                            print >> sys.stderr, orig_line
                            raise SuiteConfigError, str(x)
                        if ttype == 'async_oneoff':
                            if name not in self.async_oneoff_tasks:
                                self.async_oneoff_tasks.append(name)
                        elif ttype == 'async_repeating': 
                            if name not in self.async_repeating_tasks:
                                self.async_repeating_tasks.append(name)
                            m = re.match( '^ASYNCID:(.*)$', section )
                            asyncid_pattern = m.groups()[0]
               
                self.generate_edges( lexpression, lnames, r, ttype, cyclr, suicide )
                self.generate_taskdefs( orig_line, lnames, r, ttype, section, cyclr, asyncid_pattern )
                self.generate_triggers( lexpression, lnames, r, cyclr, asyncid_pattern, suicide )

    def generate_edges( self, lexpression, lnames, right, ttype, cyclr, suicide=False ):
        """Add nodes from this graph section to the abstract graph edges structure."""
        conditional = False
        if re.search( '\|', lexpression ):
            # plot conditional triggers differently
            conditional = True
 
        sasl = False
        for left in lnames:
            if left in self.async_oneoff_tasks + self.async_repeating_tasks:
                sasl = True
            e = edge( left, right, cyclr, sasl, suicide, conditional )
            if ttype == 'async_oneoff':
                if e not in self.async_oneoff_edges:
                    self.async_oneoff_edges.append( e )
            elif ttype == 'async_repeating':
                if e not in self.async_repeating_edges:
                    self.async_repeating_edges.append( e )
            else:
                # cycling
                self.edges.append(e)

    def generate_taskdefs( self, line, lnames, right, ttype, section, cyclr, asyncid_pattern ):
        for node in lnames + [right]:
            if not node:
                # if right is None, lefts are lone nodes
                # for which we still define the taskdefs
                continue
            try:
                name = graphnode( node ).name
                offset = graphnode( node ).offset
            except GraphNodeError, x:
                print >> sys.stderr, line
                raise SuiteConfigError, str(x)

            if name not in self['runtime']:
                if self.verbose and self.validation:
                    print >> sys.stderr, 'WARNING: task "' + name + '" is defined only by graph - it will inherit root.'
                # inherit the root runtime
                self['runtime'][name] = self['runtime']['root'].odict()
                if 'root' not in self.members:
                    # (happens when no runtimes are defined in the suite.rc)
                    self.members['root'] = []
                self.family_hierarchy[name] = [name, 'root']
                self.members['root'].append(name)

            if name not in self.taskdefs:
                try:
                    self.taskdefs[ name ] = self.get_taskdef( name )
                except taskdef.DefinitionError, x:
                    print >> sys.stderr, line
                    raise SuiteConfigError, str(x)

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
                self.taskdefs[name].cycling = True
                if name not in self.cycling_tasks:
                    self.cycling_tasks.append(name)

            if offset:
                cyc = deepcopy( cyclr )
                # this changes the cyclers internal state so we need a
                # private copy of it:
                cyc.adjust_state(offset)
            else:
                cyc = cyclr
            self.taskdefs[ name ].add_to_valid_cycles( cyc )

            if not self.simulation_mode:
                # register any explicit internal outputs
                taskconfig = self['runtime'][name]
                for lbl in taskconfig['outputs']:
                    msg = taskconfig['outputs'][lbl]
                    outp = outputx(msg,cyclr)
                    self.taskdefs[ name ].outputs.append( outp )

            # collate which tasks appear in each section
            # (used in checking conditional trigger expressions)
            if cyclr not in self.tasks_by_cycler:
                self.tasks_by_cycler[cyclr] = []
            if name not in self.tasks_by_cycler[cyclr]:
                self.tasks_by_cycler[cyclr].append(name)

    def generate_triggers( self, lexpression, lnames, right, cycler, asyncid_pattern, suicide ):
        if not right:
            # lefts are lone nodes; no more triggers to define.
            return

        conditional = False
        if re.search( '\|', lexpression ):
            conditional = True
            # For single triggers or '&'-only ones, which will be the
            # vast majority, we needn't use conditional prerequisites
            # (they may be less efficient due to python eval at run time).

        ctrig = {}
        cname = {}
        for left in lnames:
            lnode = graphnode(left)  # (GraphNodeError checked above)
            if lnode.intercycle:
                self.taskdefs[lnode.name].intercycle = True

            trigger = self.set_trigger( lnode.name, right, lnode.output, lnode.offset, asyncid_pattern, suicide )
            if not trigger:
                continue
            if not conditional:
                self.taskdefs[right].add_trigger( trigger, cycler )  
                continue

            # CONDITIONAL TRIGGERS
            if trigger.async_repeating:
                # (extend taskdef.py:tclass_add_prerequisites to allow this)
                raise SuiteConfigError, 'ERROR, ' + left + ': repeating async tasks are not allowed in conditional triggers.'
            # Use fully qualified name for the expression label
            # (task name is not unique, e.g.: "F | F:fail => G")
            label = re.sub( '[-\[\]:]', '_', left )
            ctrig[label] = trigger
            cname[label] = lnode.name

        if not conditional:
            return
        # Conditional expression must contain all start-up (or async)
        # tasks, or none - cannot mix with cycling tasks in the same
        # expression. Count number of start-up or async_oneoff tasks:
        countx = 0
        for label in ctrig:
            if right in self.cycling_tasks:
                if (cname[label] in self['scheduling']['special tasks']['start-up'] or \
                        cname[label] in self.async_oneoff_tasks ):
                    countx += 1
        if countx > 0 and countx != len(cname.keys()):
            print >> sys.stderr, 'ERROR:', lexpression
            raise SuiteConfigError, '(start-up or async) and (cycling) tasks in same conditional'
 
        # Replace some chars for later use in regular expressions.
        expr = re.sub( '[-\[\]:]', '_', lexpression )
        self.taskdefs[right].add_conditional_trigger( ctrig, expr, cycler )

    def get_graph_raw( self, start_ctime, stop, raw=False,
            group_nodes=[], ungroup_nodes=[], ungroup_recursive=False,
            group_all=False, ungroup_all=False ):
        """Convert the abstract graph edges held in self.edges (etc.) to
        actual edges for a concrete range of cycle times."""

        if group_all:
            # Group all family nodes
            for fam in self.members:
                #if fam != 'root':
                if fam not in self.closed_families:
                    self.closed_families.append( fam )
        elif ungroup_all:
            # Ungroup all family nodes
            self.closed_families = []
        elif len(group_nodes) > 0:
            # Group chosen family nodes
            for node in group_nodes:
                if node != 'root':
                    parent = self.family_hierarchy[node][1]
                    if parent not in self.closed_families:
                        self.closed_families.append( parent )
        elif len(ungroup_nodes) > 0:
            # Ungroup chosen family nodes
            for node in ungroup_nodes:
                if node in self.closed_families:
                    self.closed_families.remove(node)
                if ungroup_recursive:
                    for fam in deepcopy(self.closed_families):
                        if fam in self.members[node]:
                            self.closed_families.remove(fam)

        # Now define the concrete graph edges (pairs of nodes) for plotting.
        gr_edges = []

        for e in self.async_oneoff_edges + self.async_repeating_edges:
            right = e.get_right(1, False, False, [], [])
            left  = e.get_left( 1, False, False, [], [])
            nl, nr = self.close_families( left, right )
            gr_edges.append( (nl, nr, False, e.suicide, e.conditional) )

        # Get actual first real cycle time for the whole suite (get all
        # cyclers to adjust the putative start time upward)
        adjusted = []
        for cyc in self.cyclers:
            if hasattr( cyc.__class__, 'is_async' ):
                # ignore asynchronous tasks
                continue
            foo = cyc.initial_adjust_up( start_ctime ) 
            adjusted.append( foo )
        if len( adjusted ) > 0:
            adjusted.sort()
            actual_first_ctime = adjusted[0]
        else:
            actual_first_ctime = start_ctime

        startup_exclude_list = self.get_coldstart_task_list() + \
                self.get_startup_task_list()

        for e in self.edges:
            # Get initial cycle time for this cycler
            ctime = e.cyclr.initial_adjust_up( start_ctime )

            while int(ctime) <= int(stop):
                # Loop over cycles generated by this cycler
                
                if ctime != actual_first_ctime:
                    not_initial_cycle = True
                else:
                    not_initial_cycle = False

                r_id = e.get_right(ctime, not_initial_cycle, raw, startup_exclude_list, [])
                l_id = e.get_left( ctime, not_initial_cycle, raw, startup_exclude_list, [])

                action = True

                if l_id == None and r_id == None:
                    # nothing to add to the graph
                    action = False

                if l_id != None and not e.sasl:
                    # check that l_id is not earlier than start time
                    # TO DO: does this invalidate r_id too?
                    tmp, lctime = l_id.split()
                    #sct = ct(start_ctime)
                    sct = ct(actual_first_ctime)
                    diffhrs = sct.subtract_hrs( lctime )
                    if diffhrs > 0:
                        action = False

                if action:
                    nl, nr = self.close_families( l_id, r_id )
                    gr_edges.append( ( nl, nr, False, e.suicide, e.conditional ) )

                # increment the cycle time
                ctime = e.cyclr.next( ctime )

        return gr_edges
 
    def get_graph( self, start_ctime, stop, colored=True, raw=False,
            group_nodes=[], ungroup_nodes=[], ungroup_recursive=False,
            group_all=False, ungroup_all=False ):

        # TO DO: this method could be put in the graphing module? It is
        # currently duplicated in xstateview.py.

        # get_graph_raw is factored out here because the graph control
        # GUI has to retrieve the raw graph, because the PyGraphviz 
        # graph object does not seem to be serializable (pickle error)
        # for Pyro.
        gr_edges = self.get_graph_raw( start_ctime, stop, raw,
                group_nodes, ungroup_nodes, ungroup_recursive,
                group_all, ungroup_all )

        # Get a graph object
        if colored:
            graph = graphing.CGraph( self.suite, self['visualization'] )
        else:
            graph = graphing.CGraphPlain( self.suite )

        # sort and then add edges in the hope that edges added in the
        # same order each time will result in the graph layout not
        # jumping around (does this help? -if not discard)
        gr_edges.sort()
        for e in gr_edges:
            l, r, dashed, suicide, conditional = e
            if conditional:
                if suicide:
                    style='dashed'
                    arrowhead='odot'
                else:
                    style='solid'
                    arrowhead='onormal'
            else:
                if suicide:
                    style='dashed'
                    arrowhead='dot'
                else:
                    style='solid'
                    arrowhead='normal'
            if dashed:
                # override
                style='dashed'

            graph.cylc_add_edge( l, r, True, style=style, arrowhead=arrowhead )

        for n in graph.nodes():
            if not colored:
                n.attr['style'] = 'filled'
                n.attr['fillcolor'] = 'cornsilk'

        return graph

    def close_families( self, nlid, nrid ):
        # Generate final node names, replacing family members with
        # family nodes if requested.

        # TO DO: FORMATTED NODE NAMES
        # can't be used until comparison with internal IDs cope
        # for gcylc (get non-formatted tasks as disconnected nodes on
        # the right of the formatted-name base graph).
        formatted=False

        lname, ltag = None, None
        rname, rtag = None, None
        nr, nl = None, None
        if nlid:
            one, two = nlid.split()
            lname = one.getstr()
            ltag = two.getstr(formatted)
            nl = nlid.getstr(formatted)
        if nrid:
            one, two = nrid.split()
            rname = one.getstr()
            rtag = two.getstr(formatted)
            nr = nrid.getstr(formatted)

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

    def load_graph( self ):
        for item in self['scheduling']['dependencies']:
            if item == 'graph':
                # asynchronous graph
                graph = self['scheduling']['dependencies']['graph']
                if graph:
                    section = "once"
                    self.parse_graph( section, graph )
            else:
                try:
                    graph = self['scheduling']['dependencies'][item]['graph']
                except KeyError:
                    pass
                else:
                    if graph:
                        section = item
                        self.parse_graph( section, graph )
 
    def parse_graph( self, section, graph ):
        self.graph_found = True
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
            # generate pygraphviz graph nodes and edges, and task definitions
            self.process_graph_line( line, section )

    def get_taskdef( self, name ):
        # (DefinitionError caught above)
        taskd = taskdef.taskdef( name )

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
        try:
            taskconfig = self['runtime'][name]
        except KeyError:
            raise SuiteConfigError, "Task not found: " + name

        # Interpolate <TASK> here (doing it earlier like <NAMESPACE>
        # fails to catch dummy tasks that are defined only by graph
        # (otherwise they would inherit root with <TASK>=root).
        self.interpolate( name, taskconfig, '<TASK>' )

        taskd.description = taskconfig['description']

        if self.simulation_mode:
            taskd.job_submit_method = self['cylc']['simulation mode']['job submission']['method']
            taskd.command = self['cylc']['simulation mode']['command scripting']
            taskd.retry_delays = deque( self['cylc']['simulation mode']['retry delays'] )
        else:
            taskd.owner = taskconfig['remote']['owner']
            taskd.job_submit_method = taskconfig['job submission']['method']
            taskd.command   = taskconfig['command scripting']
            taskd.retry_delays = deque( taskconfig['retry delays'])
            taskd.precommand = taskconfig['pre-command scripting'] 
            taskd.postcommand = taskconfig['post-command scripting'] 

        # check retry delay type (must be float):
        for i in taskd.retry_delays:
            try:
                float(i)
            except ValueError:
                raise SuiteConfigError, "ERROR, retry delay values must be floats: " + str(i)

        # initial scripting (could be required to access cylc even in sim mode).
        taskd.initial_scripting = taskconfig['initial scripting'] 

        taskd.ssh_messaging = str(taskconfig['remote']['ssh messaging'])

        taskd.job_submission_shell = taskconfig['job submission']['shell']

        taskd.job_submit_command_template = taskconfig['job submission']['command template']

        taskd.job_submit_log_directory = taskconfig['log directory']
        taskd.job_submit_share_directory = taskconfig['share directory']
        taskd.job_submit_work_directory = taskconfig['work directory']

        if not self.simulation_mode and (taskconfig['remote']['host'] or taskconfig['remote']['owner']):
            # Remote task hosting config, ignored in sim mode.
            taskd.remote_host = taskconfig['remote']['host']
            taskd.remote_shell_template = taskconfig['remote']['remote shell template']
            taskd.remote_cylc_directory = taskconfig['remote']['cylc directory']
            taskd.remote_suite_directory = taskconfig['remote']['suite definition directory']
            if taskconfig['remote']['log directory']:
                # (Unlike for the work and share directories below, we
                # need to retain local and remote log directory paths - 
                # the local one is still used for the task job script). 
                taskd.remote_log_directory  = taskconfig['remote']['log directory']
            else:
                # Use local log directory path, but replace home dir
                # (if present) with literal '$HOME' for interpretation
                # on the remote host.
                taskd.remote_log_directory  = re.sub( self.homedir, '$HOME', taskd.job_submit_log_directory )

            if taskconfig['remote']['work directory']:
                # Replace local work directory.
                taskd.job_submit_work_directory  = taskconfig['remote']['work directory']
            else:
                # Use local work directory path, but replace home dir
                # (if present) with literal '$HOME' for interpretation
                # on the remote host.
                taskd.job_submit_work_directory  = re.sub( self.homedir, '$HOME', taskd.job_submit_work_directory )

            if taskconfig['remote']['share directory']:
                # Replace local share directory.
                taskd.job_submit_share_directory  = taskconfig['remote']['share directory']
            else:
                # Use local share directory path, but replace home dir
                # (if present) with literal '$HOME' for interpretation
                # on the remote host.
                taskd.job_submit_share_directory  = re.sub( self.homedir, '$HOME', taskd.job_submit_share_directory )

        taskd.manual_messaging = taskconfig['manual completion']

        if not self.simulation_mode or self['cylc']['simulation mode']['event hooks']['enable']:
            # configure task event hooks
            taskd.hook_script = taskconfig['event hooks']['script']
            taskd.hook_events = taskconfig['event hooks']['events']
            for event in taskd.hook_events:
                if event not in ['submitted', 'started', 'succeeded', 'warning', 'failed', 'retry', \
                        'submission_failed', 'submission_timeout', 'execution_timeout' ]:
                    raise SuiteConfigError, name + ": illegal task event: " + event
            taskd.submission_timeout = taskconfig['event hooks']['submission timeout']
            taskd.execution_timeout  = taskconfig['event hooks']['execution timeout']
            taskd.reset_timer = taskconfig['event hooks']['reset timer']

        if self.validation and len(taskd.hook_events) == 0 and taskd.hook_script:
            # this is not a fatal error
            print >> sys.stderr, "WARNING: task event handler specified without events to handle."
        if len(taskd.hook_events) > 0 and not taskd.hook_script:
            # but this is
            raise SuiteConfigError, "ERROR, no handler specified for these task events: " + ','.join(taskd.hook_events)

        if 'submission_timeout' in taskd.hook_events and not taskd.submission_timeout:
            print >> sys.stderr, 'WARNING:', taskd.name, 'job submission timeout disabled (no timeout given)'
        if 'execution_timeout' in taskd.hook_events and not taskd.execution_timeout:
            print >> sys.stderr, 'WARNING:', taskd.name, 'job execution timeout disabled (no timeout given)'
         
        taskd.logfiles    = taskconfig[ 'extra log files' ]
        taskd.resurrectable = taskconfig[ 'enable resurrection' ]

        taskd.environment = taskconfig[ 'environment' ]
        self.check_environment( taskd.name, taskd.environment )

        taskd.directives  = taskconfig[ 'directives' ]

        foo = deepcopy(self.family_hierarchy[ name ])
        foo.reverse()
        taskd.namespace_hierarchy = foo

        return taskd

    def check_environment( self, name, env ):
        bad = []
        for varname in env:
            if not re.match( '^[a-zA-Z_][\w]*$', varname ):
                bad.append(varname)
        if len(bad) != 0:
            for item in bad:
                print >> sys.stderr, " ", item
            raise SuiteConfigError("ERROR: illegal environment variable name(s) detected in namespace " + name )
    
    def get_task_proxy( self, name, ctime, state, stopctime, startup ):
        try:
            tdef = self.taskdefs[name]
        except KeyError:
            raise TaskNotDefinedError("ERROR, No such task name: " + name )
        return tdef.get_task_class()( ctime, state, stopctime, startup )

    def get_task_proxy_raw( self, name, tag, state, stoptag, startup ):
        # Used by 'cylc submit' to submit tasks defined by runtime
        # config but not currently present in the graph (so we must
        # assume that the given tag is valid for the task).
        try:
            truntime = self['runtime'][name]
        except KeyError:
            raise TaskNotDefinedError("ERROR, task not defined: " + name )
        tdef = self.get_taskdef( name )
        try:
            foo = ct(tag)
        except CycleTimeError, x:
            # must be async
            tdef.type = 'async_oneoff'
        else:
            # assume input cycle is valid
            tdef.hours = [ int( foo.hour ) ]
        return tdef.get_task_class()( tag, state, stoptag, startup )

    def get_task_class( self, name ):
        return self.taskdefs[name].get_task_class()
