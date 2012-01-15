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

# TO DO: document use foo[T-6]:out1, not foo:out1 with
# <CYLC_TASK_CYCLE_TIME-6> in the output message.

# TO DO: document that cylc hour sections must be unique, but can
# overlap: [[[0]]] and [[[0,12]]]; but if the same dependency is 
# defined twice it will result in a "duplicate prerequisite" error.

# TO DO: check that mid-level families used in the graph are replaced
# by *task* members, not *family* members.

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
from cylc.print_tree import print_tree

try:
    from jinja2 import Environment, FileSystemLoader, TemplateError
except ImportError:
    jinja2_loaded = False
else:
    jinja2_loaded = True

try:
    import graphing
except:
    graphing_disabled = True
else:
    graphing_disabled = False

def include_files( inf, dir ):
    outf = []
    for line in inf:
        m = re.match( '\s*%include\s+(.*)\s*$', line )
        if m:
            # include statement found
            match = m.groups()[0]
            # strip off possible quotes: %include "foo.inc"
            match = match.replace('"','')
            match = match.replace("'",'')
            inc = os.path.join( dir, match )
            if os.path.isfile(inc):
                #print "Inlining", inc
                h = open(inc, 'rb')
                inc = h.readlines()
                h.close()
                # recursive inclusion
                outf.extend( include_files( inc, dir ))
            else:
                raise ConfigObjError, "ERROR, Include-file not found: " + inc
        else:
            # no match
            outf.append( line )
    return outf

def continuation_lines( inf ):
    outf = []
    cline = ''
    for line in inf:
        # detect continuation line endings
        m = re.match( '(.*)\\\$', line )
        if m:
            # add line to cline instead of appending to outf.
            cline += m.groups()[0]
        else:
            outf.append( cline + line )
            # reset cline 
            cline = ''
    return outf

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

    def __init__( self, suite, suiterc, simulation_mode=False, verbose=False, collapsed=[] ):
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
            print "LOADING suite.rc"
        f = open( self.file )
        flines = f.readlines()
        f.close()
        # handle cylc include-files
        flines = include_files( flines, self.dir )

        # check first line of file for template engine directive
        # (check for new empty suite.rc files - zero lines - first)
        if flines and re.match( '^#![jJ]inja2\s*', flines[0] ):
            # This suite.rc file requires processing with jinja2.
            if not jinja2_loaded:
                print >> sys.stderr, 'ERROR: This suite requires processing with the Jinja2 template engine'
                print >> sys.stderr, 'ERROR: but the Jinja2 modules are not installed in your PYTHONPATH.'
                raise SuiteConfigError, 'Aborting (Jinja2 required).'
            if self.verbose:
                print "Processing the suite with Jinja2"
            env = Environment( loader=FileSystemLoader(self.dir) )
             # load file lines into a template, excluding '#!jinja2' so
             # that '#!cylc-x.y.z' rises to the top.
            try:
                template = env.from_string( ''.join(flines[1:]) )
            except TemplateError, x:
                raise SuiteConfigError, "Jinja2 template error: " + str(x)

            try:
                # (converting unicode to plain string; configobj doesn't like?)
                suiterc = str( template.render() )
            except Exception, x:
                raise SuiteConfigError, "ERROR: Jinja2 template rendering failed: " + str(x)

            suiterc = suiterc.split('\n') # pass a list of lines to configobj
        else:
            # This is a plain suite.rc file.
            suiterc = flines

        # handle cylc continuation lines
        suiterc = continuation_lines( suiterc )

        try:
            CylcConfigObj.__init__( self, suiterc, configspec=self.spec )
        except ConfigObjError, x:
            raise SuiteConfigError, x

        if self.verbose:
            print "VALIDATING against the suite.rc specification."
        # validate and convert to correct types
        val = Validator()
        test = self.validate( val, preserve_errors=True )
        if test != True:
            # Validation failed
            failed_items = flatten_errors( self, test )
            # Always print reason for validation failure
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

        if self.verbose:
            print "PARSING clock-triggered tasks"
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
            print "PARSING runtime name lists"
        # If a runtime section heading is a list of names then the
        # subsequent config applies to each member. Copy the config
        # for each member and replace any occurrence of '<TASK>' with
        # the actual task name.
        for item in self['runtime']:
            if re.search( ',', item ):
                # list of task names
                task_names = re.split(', *', item )
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
            print "PARSING the runtime namespace hierarchy"

        # RUNTIME INHERITANCE
        for label in self['runtime']:
            hierarchy = []
            name = label
            self.interpolate( item, self['runtime'][name], '<NAMESPACE>' )
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

        for item in self['runtime']:
            self.interpolate( item, self['runtime'][item], '<TASK>' )

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

        self.process_directories()
        self.load()

        self.family_tree = {}
        self.task_runtimes = {}
        self.define_inheritance_tree( self.family_tree, self.family_hierarchy )
        self.prune_inheritance_tree( self.family_tree, self.task_runtimes )

        self.__check_tasks()

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
  
    def get_inheritance( self ):
        inherit = {}
        for ns in self['runtime']:
            #if 'inherit' in self['runtime'][ns]:
            inherit[ns] = self['runtime'][ns]['inherit']
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

    def process_directories(self):
        # Environment variable interpolation in directory paths.
        # (allow use of suite identity variables):
        os.environ['CYLC_SUITE_REG_NAME'] = self.suite
        # registration.delimiter_re ('\.') removed to avoid circular import!
        os.environ['CYLC_SUITE_REG_PATH'] = re.sub( '\.', '/', self.suite )
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
        # replace '<TASK>' with 'name' in all items.
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

    def set_trigger( self, task_name, output_name=None, offset=None, asyncid_pattern=None ):
        if output_name and not self.simulation_mode:
            # (ignore internal outputs in sim mode - dummy tasks don't know about them).
            try:
                trigger = self['runtime'][task_name]['outputs'][output_name]
            except KeyError:
                if output_name == 'fail':
                    trigger = task_name + '%<TAG> failed'
                else:
                    raise SuiteConfigError, "ERROR: Task '" + task_name + "' does not define output '" + output_name  + "'"
            else:
                # replace <CYLC_TASK_CYCLE_TIME> with <TAG> in explicit outputs
                trigger = re.sub( 'CYLC_TASK_CYCLE_TIME', 'TAG', trigger )
        else:
            trigger = task_name + '%<TAG> succeeded'

        # now adjust for cycle time or tag offset
        if offset:
            trigger = re.sub( 'TAG', 'TAG - ' + str(offset), trigger )
            # extract multiple offsets:
            m = re.match( '(.*)<TAG\s*(.*)>(.*)', trigger )
            if m:
                pre, combo, post = m.groups()
                combo = eval( combo )
                if combo == 0:
                    trigger = pre + '<TAG>' + post
                elif combo > 0:
                    trigger = pre + '<TAG + ' + str(combo) + '>' + post
                else:
                    # '-' appears in combo
                    trigger = pre + '<TAG ' + str(combo) + '>' + post

        # for oneoff async tasks, replace '<TAG>' with '1' (NECESS?)
        if task_name in self.async_oneoff_tasks:
            trigger = re.sub( '<TAG>', '1', trigger )

        if asyncid_pattern:
            trigger = re.sub( '<ASYNCID>', '(' + asyncid_pattern + ')', trigger )
 
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
            d = self['runtime'][item]['job submission']['log directory']
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
        # return full list of *task* (runtime hierarchy leaves) names 
        tasknames = self.task_runtimes.keys()
        tasknames.sort(key=str.lower)  # case-insensitive sort
        return tasknames

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
                    print >> sys.stderr, 'ERROR: synchronous special tasks cannot be used in an asynchronous graph section:'
                    print >> sys.stderr, '      ', ', '.join(bad)
                    raise SuiteConfigError, 'ERROR: inconsistent use of special task types.'

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
                graph.cylc_add_node( r, True )
            elif r == None:
                graph.cylc_add_node( l, True )
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
                graph.cylc_add_edge( l, r, True, style=style, arrowhead=arrowhead )

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
                # generate pygraphviz graph nodes and edges, and task definitions
                self.process_graph_line( line, section )

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
        try:
            taskconfig = self['runtime'][name]
        except KeyError:
            raise SuiteConfigError, "Task not found: " + name
        taskd.description = taskconfig['description']

        if self.simulation_mode:
            taskd.job_submit_method = self['cylc']['simulation mode']['job submission']['method']
            taskd.commands = self['cylc']['simulation mode']['command scripting']
        else:
            for lbl in taskconfig['outputs']:
                # register internal outputs, replacing <CYLC_TASK_CYCLE_TIME> with <TAG>
                # (ignored in sim mode - dummy tasks don't know about internal outputs).
                taskd.outputs.append( re.sub( 'CYLC_TASK_CYCLE_TIME', 'TAG', taskconfig['outputs'][lbl] ))
            taskd.owner = taskconfig['remote']['owner']
            taskd.job_submit_method = taskconfig['job submission']['method']
            taskd.commands   = taskconfig['command scripting']
            taskd.precommand = taskconfig['pre-command scripting'] 
            taskd.postcommand = taskconfig['post-command scripting'] 
        # initial scripting could be required to access cylc, even in sim mode.
        taskd.initial_scripting = taskconfig['initial scripting'] 

        taskd.job_submission_shell = taskconfig['job submission']['shell']

        taskd.job_submit_command_template = taskconfig['job submission']['command template']

        taskd.job_submit_log_directory = taskconfig['job submission']['log directory']
        taskd.job_submit_share_directory = taskconfig['job submission']['share directory']
        taskd.job_submit_work_directory = taskconfig['job submission']['work directory']

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
                taskd.remote_log_directory  = re.sub( os.environ['HOME'], '$HOME', taskd.job_submit_log_directory )

            if taskconfig['remote']['work directory']:
                # Replace local work directory.
                taskd.job_submit_work_directory  = taskconfig['remote']['work directory']
            else:
                # Use local work directory path, but replace home dir
                # (if present) with literal '$HOME' for interpretation
                # on the remote host.
                taskd.job_submit_work_directory  = re.sub( os.environ['HOME'], '$HOME', taskd.job_submit_work_directory )

            if taskconfig['remote']['share directory']:
                # Replace local share directory.
                taskd.job_submit_share_directory  = taskconfig['remote']['share directory']
            else:
                # Use local share directory path, but replace home dir
                # (if present) with literal '$HOME' for interpretation
                # on the remote host.
                taskd.job_submit_share_directory  = re.sub( os.environ['HOME'], '$HOME', taskd.job_submit_share_directory )

        taskd.manual_messaging = taskconfig['manual completion']

        if not self.simulation_mode or self['cylc']['simulation mode']['event hooks']['enable']:
            taskd.hook_script = taskconfig['event hooks']['script']
            taskd.hook_events = taskconfig['event hooks']['events']
            for event in taskd.hook_events:
                if event not in ['submitted', 'started', 'succeeded', 'failed', 'submission_failed', 'timeout' ]:
                    raise SuiteConfigError, name + ": illegal event hook: " + event
            taskd.submission_timeout = taskconfig['event hooks']['submission timeout']
            taskd.execution_timeout  = taskconfig['event hooks']['execution timeout']
            taskd.reset_timer = taskconfig['event hooks']['reset timer']

        if len(taskd.hook_events) > 0 and not taskd.hook_script:
            print >> sys.stderr, 'WARNING:', taskd.name, 'defines hook events but no hook script'
        if taskd.execution_timeout or taskd.submission_timeout or taskd.reset_timer:
            if 'timeout' not in taskd.hook_events:
                print >> sys.stderr, 'WARNING:', taskd.name, 'configures timeouts but does not handle timeout events'
            if not taskd.hook_script:
                print >> sys.stderr, 'WARNING:', taskd.name, 'configures timeouts but no hook script'
        
        taskd.logfiles    = taskconfig[ 'extra log files' ]
        taskd.environment = taskconfig[ 'environment' ]
        taskd.directives  = taskconfig[ 'directives' ]

        foo = deepcopy(self.family_hierarchy[ name ])
        foo.reverse()
        taskd.namespace_hierarchy = foo

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
