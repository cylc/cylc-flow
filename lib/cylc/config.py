#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

# NOTE: configobj.reload() apparently does not revalidate (list-forcing
# is not done, for example, on single value lists with no trailing
# comma) ... so to reparse the file  we have to instantiate a new config
# object.

# For future reference, I attempted flattening each namespace dict prior
# to inheritance processing, and expanding again after, to allow
# copy-and-override of shallow rather than nested dicts, but got no
# appreciable speedup.

import re, os, sys
import taskdef
from envvar import check_varnames, expandvars
from copy import deepcopy, copy
from OrderedDict import OrderedDict
from cycle_time import ct, CycleTimeError
from mkdir_p import mkdir_p
from validate import Validator
from output import outputx
from configobj import get_extra_values, flatten_errors, Section, ConfigObj
from cylcconfigobj import CylcConfigObj, ConfigObjError
from graphnode import graphnode, GraphNodeError
from print_tree import print_tree
from prerequisites.conditionals import TriggerExpressionError
from regpath import RegPath
from trigger import triggerx
from continuation_lines import join
from include_files import inline, IncludeFileError
from dictcopy import replicate, override
from TaskID import TaskID
from C3MRO import C3

try:
    import graphing
except ImportError:
    graphing_disabled = True
else:
    graphing_disabled = False

try:
    from Jinja2Support import Jinja2Process, TemplateError, TemplateSyntaxError
except ImportError:
    jinja2_disabled = True
else:
    jinja2_disabled = False

def str2list( st ):
    if isinstance(st, list):
        return st
    return re.split( '[, ]+', st )

def str2bool( st ):
    return str(st).lower() in ( 'true' )

def str2float( st ):
    return float( st )

def coerce_runtime_values( rdict ):
    """Coerce non-string values as would be done by [runtime]
    validation. This must be kept up to date with any new non-string
    items added the runtime configspec."""

    # coerce list values from string
    for item in [
        'inherit',
        'retry delays',
        'extra log files',
        ( 'job submission', 'retry delays' ),
        ( 'simulation mode', 'run time range' ) ]:
        try:
            if isinstance( item, tuple ):
                rdict[item[0]][item[1]] = str2list( rdict[item[0]][item[1]] )
            else:
                rdict[item] = str2list( rdict[item] )
        except KeyError:
            pass

    # coerce bool values from string
    for item in [
        'manual completion',
        'enable resurrection',
        ( 'simulation mode', 'simulate failure' ),
        ( 'simulation mode', 'disable task event hooks' ),
        ( 'simulation mode', 'disable retries' ),
        ( 'dummy mode', 'disable pre-command scripting' ),
        ( 'dummy mode', 'disable post-command scripting' ),
        ( 'dummy mode', 'disable task event hooks' ),
        ( 'dummy mode', 'disable retries' ),
        ( 'event hooks', 'reset timer' ) ]:
        try:
            if isinstance( item, tuple ):
                rdict[item[0]][item[1]] = str2bool( rdict[item[0]][item[1]] )
            else:
                rdict[item] = str2bool( rdict[item] )
        except KeyError:
            pass

    # coerce float values from string
    for item in [
            ('event hooks', 'submission timeout' ),
            ('event hooks', 'execution timeout' ) ]:
        try:
            if isinstance( item, tuple ):
                rdict[item[0]][item[1]] = str2float( rdict[item[0]][item[1]] )
            else:
                rdict[item] = str2float( rdict[item] )
        except KeyError:
            pass

class SuiteConfigError( Exception ):
    """
    Attributes:
        message - what the problem is. 
        TODO - element - config element causing the problem
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class TaskNotDefinedError( SuiteConfigError ):
    pass

# TODO: separate config for run and non-run purposes?

class config( CylcConfigObj ):
    """Parse and validate a suite definition, and compute everything
    needed to create task proxy classes, the suite graph structure,
    etc."""

    def __init__( self, suite, suiterc, template_vars=[],
            template_vars_file=None, owner=None, run_mode='live',
            verbose=False, validation=False, strict=False, collapsed=[] ):

        self.run_mode = run_mode
        self.verbose = verbose
        self.strict = strict
        self.naked_dummy_tasks = []
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

        self.upgrades = [
                ( '5.2.0', self.upgrade_5_2_0 ) ]
        self.deprecation_warnings = {}

        # runtime hierarchy dicts keyed by namespace name:
        self.runtime = {
                # lists of parent namespaces
                'parents' : {},
                # lists of C3-linearized ancestor namespaces
                'linearized ancestors' : {},
                # lists of first-parent ancestor namepaces
                'first-parent ancestors' : {},
                # lists of all descendant namespaces
                'descendants' : {},
                # lists of all descendant namespaces from the first-parent hierarchy
                'first-parent descendants' : {}
                }
        # (first-parents are used for visualization purposes)
        # (tasks - leaves on the tree - do not appear in 'descendants')

        self.families_used_in_graph = []

        self.suite = suite
        self.file = suiterc
        self.dir = os.path.dirname(suiterc)

        self.owner = owner

        if self.verbose:
            print "Loading suite.rc"

        if not os.path.isfile( self.file ):
            raise SuiteConfigError, 'File not found: ' + self.file

        f = open( self.file )
        flines = f.readlines()
        f.close()

        # handle cylc include-files
        try:
            flines = inline( flines, self.dir )
        except IncludeFileError, x:
            raise SuiteConfigError( str(x) )

        if flines and re.match( '^#![jJ]inja2\s*', flines[0] ):
            # Jinja2 template processing, if first line is "#![jJ]inja2"
            if jinja2_disabled:
                print >> sys.stderr, 'ERROR: This is a "#!jinja2" suite, but Jinja2 is not installed'
                raise SuiteConfigError( 'Aborting (Jinja2 required).')
            if verbose:
                print "Processing the suite with Jinja2"

            try:
                suiterc = Jinja2Process( flines, self.dir, template_vars, template_vars_file, self.verbose )
            except TemplateSyntaxError, x:
                lineno = x.lineno + 1  # (flines array starts from 0)
                print >> sys.stderr, 'Jinja2 Template Syntax Error, line', lineno
                print >> sys.stderr, flines[x.lineno]
                raise SystemExit(str(x))
            except TemplateError, x:
                print >> sys.stderr, 'Jinja2 Template Error'
                raise SystemExit(x)
            except TypeError, x:
                print >> sys.stderr, 'Jinja2 Type Error'
                raise SystemExit(x)
        else:
            # plain cylc suite definition
            suiterc = flines

        # handle cylc continuation lines
        suiterc = join( suiterc )

        # parse the file into a sparse data structure
        try:
            CylcConfigObj.__init__( self, suiterc, interpolation=False )
        except ConfigObjError, x:
            raise SuiteConfigError, x

        # on-the-fly backward compatibility translations
        for vn,upgr in self.upgrades:
            warnings = upgr( self )
            if warnings:
                self.deprecation_warnings[vn] = warnings
        if self.validation:
            self.print_deprecation_warnings()

        # now validate and load defaults for each section in turn
        # (except [runtime] - see below).
        head = {}
        for key, val in self.items():
            if key == 'cylc' or \
                    key == 'scheduling' or \
                    key == 'runtime' or \
                    key == 'visualization' or \
                    key == 'development':
                        continue
            head[key] = val

        for item, val in self.validate_section( head, 'head.spec' ).items():
            self[item] = val

        for sec in [ 'cylc', 'scheduling', 'visualization', 'development' ]:
            if sec in self:
                cfg = self[sec]
            else:
                cfg = OrderedDict()
            for item, val in self.validate_section( {sec:cfg}, sec + '.spec' ).items():
                self[item] = val

        if 'runtime' not in self.keys():
            self['runtime'] = OrderedDict()

        # [runtime] validation loads the complete defaults dict into
        # every namespace, so just do it for explicit validation.  
        if self.validation:
            for name in self['runtime']:
                cfg = OrderedDict()
                replicate( cfg, self['runtime'][name].odict())
                self.validate_section( { 'runtime': { name: cfg }}, 'runtime.spec' )

        # coerce non-string [runtime] values manually, as validation would have done
        for ns in self['runtime']:
            coerce_runtime_values( self['runtime'][ns] )

        if 'root' not in self['runtime']:
            self['runtime']['root'] = OrderedDict()

        # load defaults into one namespace dict
        cfg = OrderedDict()
        dense = self.validate_section( { 'runtime': { 'defaults': cfg }}, 'runtime.spec' )
        self.runtime_defaults = dense['runtime']['defaults']

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
                replicate( tconfig, self['runtime'][item].odict() )
                # record it under the task name
                self['runtime'][name] = tconfig
            # delete the original multi-task section
            del self['runtime'][item]

        self.check_env()

        self.compute_family_tree()

        self.compute_inheritance()
        #debugging:
        #self.print_inheritance()

        collapsed_rc = self['visualization']['collapsed families']
        if len( collapsed ) > 0:
            # this overrides the rc file item
            self.closed_families = collapsed
        else:
            self.closed_families = collapsed_rc
        for cfam in self.closed_families:
            if cfam not in self.runtime['descendants']:
                print >> sys.stderr, 'WARNING, [visualization][collapsed families]: ignoring ' + cfam + ' (not a family)'
                self.closed_families.remove( cfam )
        self.vis_families = list(self.closed_families)

        # suite event hooks
        if self.run_mode == 'live' or \
                ( self.run_mode == 'simulation' and not self['cylc']['simulation mode']['disable suite event hooks'] ) or \
                ( self.run_mode == 'dummy' and not self['cylc']['dummy mode']['disable suite event hooks'] ):
            self.event_handlers = {
                    'startup'  : self['cylc']['event hooks']['startup handler'],
                    'timeout'  : self['cylc']['event hooks']['timeout handler'],
                    'shutdown' : self['cylc']['event hooks']['shutdown handler']
                    }
            self.suite_timeout = self['cylc']['event hooks']['timeout']
            self.reset_timer = self['cylc']['event hooks']['reset timer']
            self.abort_on_timeout = self['cylc']['event hooks']['abort on timeout']
            self.abort_if_startup_handler_fails = self['cylc']['event hooks']['abort if startup handler fails']
            self.abort_if_timeout_handler_fails = self['cylc']['event hooks']['abort if timeout handler fails']
            self.abort_if_shutdown_handler_fails = self['cylc']['event hooks']['abort if shutdown handler fails']
        else:
            self.event_handlers = {
                    'startup'  : None,
                    'timeout'  : None,
                    'shutdown' : None
                    }
            self.suite_timeout = None
            self.reset_timer = False
            self.abort_on_timeout = None
            self.abort_if_startup_handler_fails = False
            self.abort_if_timeout_handler_fails = False
            self.abort_if_shutdown_handler_fails = False

        self.process_directories()

        self.load_graph()

        if not self.graph_found:
            raise SuiteConfigError, 'No suite dependency graph defined.'

        self.compute_runahead_limit()

        self.configure_queues()

        # Warn or abort (if --strict) if naked dummy tasks (no runtime
        # section) are found in graph or queue config. 
        if len( self.naked_dummy_tasks ) > 0:
            if self.strict or self.verbose:
                print >> sys.stderr, 'WARNING: naked dummy tasks detected (no entry under [runtime]):'
                for ndt in self.naked_dummy_tasks:
                    print >> sys.stderr, '  +', ndt
            if self.strict:
                raise SuiteConfigError, 'ERROR: strict validation fails naked dummy tasks'

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

        ngs = self['visualization']['node groups']

        # If any existing node group member is a family, include its descendants too.
        replace = {}
        for ng, mems in ngs.items():
            replace[ng] = []
            for mem in mems:
                replace[ng] += [mem]
                if mem in self.runtime['descendants']:
                    replace[ng] += self.runtime['descendants'][mem]
        for ng in replace:
            ngs[ng] = replace[ng]

        # Define family node groups automatically so that family and
        # member nodes can be styled together using the family name.
        # Users can override this for individual nodes or sub-groups.
        for fam in self.runtime['descendants']:
            if fam not in ngs:
                ngs[fam] = [fam] + self.runtime['descendants'][fam]
 
        # (Note that we're retaining 'default node attributes' even
        # though this could now be achieved by styling the root family,
        # because putting default attributes for root in the suite.rc spec
        # results in root appearing last in the ordered dict of node
        # names, so it overrides the styling for lesser groups and
        # nodes, whereas the reverse is needed - fixing this would
        # require reordering task_attr in lib/cylc/graphing.py).

    def upgrade_5_2_0( self, cfg ):
        """Upgrade methods should upgrade to the latest (not next)
        version; then if we run them from oldest to newest we will avoid
        generating multiple warnings for items that changed several times.

        Upgrade methods are handed sparse cfg structures - i.e. just
        what is set in the file - so don't assume the presence of any
        items. It is assumed that the cfgspec will always be up to date.
        """

        warnings = []

        # [cylc][event handler execution] -> [cylc][event handler submission]
        try:
            old = cfg['cylc']['event handler execution']
        except:
            pass
        else:
            warnings.append( "[cylc][event handler execution] -> [cylc][event handler submission]" )
            del cfg['cylc']['event handler execution']
            cfg['cylc']['event handler submission'] = old

        return warnings

    def print_deprecation_warnings( self ):
        if not self.deprecation_warnings:
            return

        print >> sys.stderr, """
*** SUITE DEFINITION DEPRECATION WARNING ***
Some translations were performed on the fly."""
        if self.deprecation_warnings:
            print >> sys.stderr, "*** Please upgrade your suite definition"
        for vn, warnings in self.deprecation_warnings.items():
            for w in warnings:
                print >> sys.stderr, " * (" + vn + ")", w
        print

    def check_env( self ):
        # check environment variables now to avoid checking inherited
        # variables multiple times.
         bad = {}
         for label in self['runtime']:
             res = []
             if 'environment' in self['runtime'][label]:
                 res = check_varnames( self['runtime'][label]['environment'] )
             if res:
                 bad[label] = res
         if bad:
             print >> sys.stderr, "ERROR, bad env variable names:"
             for label, vars in bad.items():
                 print >> sys.stderr, 'Namespace:', label
                 for var in vars:
                     print >> sys.stderr, "  ", var
             raise SuiteConfigError("Illegal env variable name(s) detected" )

    def compute_family_tree( self ):
        first_parents = {}
        demoted = {}
        for name in self['runtime']:
            if name == 'root':
                self.runtime['parents'][name] = []
                first_parents[name] = []
                continue
            # get declared parents, with implicit inheritance from root.
            pts = self['runtime'][name].get( 'inherit', ['root'] )
            for p in pts:
                if p == "None":
                    # see just below
                    continue
                if p not in self['runtime']:
                    raise SuiteConfigError, "ERROR, undefined parent for " + name +": " + p
            if pts[0] == "None":
                demoted[name] = pts[1]
                pts = pts[1:]
                first_parents[name] = ['root']
            else:
                first_parents[name] = [ pts[0] ]
            self.runtime['parents'][name] = pts

        if self.verbose and demoted:
            print "First parent(s) demoted to secondary:"
            for n,p in demoted.items():
                print " +", p, "as parent of '" + n + "'"

        c3 = C3( self.runtime['parents'] )
        c3_single = C3( first_parents )

        for name in self['runtime']:
            self.runtime['linearized ancestors'][name] = c3.mro(name)
            self.runtime['first-parent ancestors'][name] = c3_single.mro(name)

        for name in self['runtime']:
            ancestors = self.runtime['linearized ancestors'][name]
            for p in ancestors[1:]:
                if p not in self.runtime['descendants']: 
                    self.runtime['descendants'][p] = []
                if name not in self.runtime['descendants'][p]:
                    self.runtime['descendants'][p].append(name)
            first_ancestors = self.runtime['first-parent ancestors'][name]
            for p in first_ancestors[1:]:
                if p not in self.runtime['first-parent descendants']: 
                    self.runtime['first-parent descendants'][p] = []
                if name not in self.runtime['first-parent descendants'][p]:
                    self.runtime['first-parent descendants'][p].append(name)

        #for name in self['runtime']:
        #    print name, self.runtime['linearized ancestors'][name]

    def compute_inheritance( self, use_simple_method=True ):

        if self.verbose:
            print "Parsing the runtime namespace hierarchy"

        results = {}
        n_reps = 0

        already_done = {} # to store already computed namespaces by mro

        for ns in self['runtime']:
            # for each namespace ...

            hierarchy = copy(self.runtime['linearized ancestors'][ns])
            hierarchy.reverse()

            result = OrderedDict()

            if use_simple_method:
                # Go up the linearized MRO from root, replicating or
                # overriding each namespace element as we go. 
                for name in hierarchy:
                    replicate( result, self['runtime'][name].odict() )
                    n_reps += 1

            else:
                # As for the simple method, but store the result of each
                # completed MRO (full or partial) as we go, and re-use
                # these wherever possible. This ought to be a lot more
                # efficient for big namespaces (e.g. lots of environment
                # variables) in deep hiearchies, but results may vary...
                prev_shortcut = False
                mro = []
                for name in hierarchy:
                    mro.append(name)
                    i_mro = '*'.join(mro)
                    if i_mro in already_done:
                        ad_result = already_done[i_mro]
                        prev_shortcut = True
                    else:
                        if prev_shortcut:
                            prev_shortcut = False
                            # copy ad_result (to avoid altering already_done)
                            result = OrderedDict() # zero the result here...
                            replicate(result,ad_result) # ...and use stored
                            n_reps += 1
                        # override name content into tmp
                        replicate( result, self['runtime'][name].odict() )
                        n_reps += 1
                        # record this mro as already done
                        already_done[i_mro] = result
    
            results[ns] = result

        # replace pre-inheritance namespaces with the post-inheritance result
        self['runtime'] = results

        # uncomment this to compare the simple and efficient methods
        # print '  Number of namespace replications:', n_reps

    def print_inheritance(self):
        for foo in self.runtime:
            print '  ', foo
            for item, val in self.runtime[foo].items():
                print '  ', '  ', item, val

    def compute_runahead_limit( self ):
        # take the smallest of the default limits from each graph section
        rl = None
        if len(self.cyclers) != 0:
            # runahead limit is only relevant for cycling sections

            rl = self['scheduling']['runahead limit']
            if rl:
                if self.verbose:
                    print "Configured runahead limit: ", rl, "hours"
            else:
                rls = []
                for cyc in self.cyclers:
                    rahd = cyc.get_min_cycling_interval()
                    if rahd:
                        rls.append(rahd)
                if len(rls) > 0:
                    # twice the minimum cycling internal in the suite
                    rl = 2 * min(rls)
                    if self.verbose:
                        print "Computed runahead limit:", rl, "hours"
        self.runahead_limit = rl

    def get_runahead_limit( self ):
        # may be None (no cycling tasks)
        return self.runahead_limit

    def validate_section( self, cfg, spec ):

        spec = os.path.join( os.environ[ 'CYLC_DIR' ], 'conf', 'suiterc', spec )

        # (note it is *validation* that fills out the dense structure)
        dense = ConfigObj( cfg, interpolation=False, configspec=spec )
        # validate and convert to correct types
        val = Validator()
        test = dense.validate( val, preserve_errors=True )
        if test != True:
            # Validation failed
            failed_items = flatten_errors( dense, test )
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
        for sections, name in get_extra_values(dense):
            # !!! TODO - THE FOLLOWING FROM CONFIGOBJ DOC SECTION 15.1 FAILS 
            ### this code gets the extra values themselves
            ##the_section = dense
            ##for section in sections:
            ##    the_section = dense[section]   #<------!!! KeyError !!!
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

        return dense

    def get_config_all_tasks( self, args, sparse=False ):
        res = {}
        for t in self.get_task_name_list():
            res[t] = self.get_config( [ 'runtime', t ] + args, sparse )
        return res

    def get_config( self, args, sparse=False ):
        if args[0] == 'runtime' and not sparse:
            # load and override runtime defaults
            if len(args) > 1:
                # a single namespace
                rtcfg = {}
                replicate( rtcfg, self.runtime_defaults )
                override( rtcfg, self['runtime'][args[1]] )
                target = rtcfg
                keys = args[2:]
            else:
                # all namespaces requested
                target = {}
                keys = []
                for ns in self['runtime'].keys():
                    rtcfg = {}
                    replicate( rtcfg, self.runtime_defaults )
                    override( rtcfg, self['runtime'][ns] )
                    target[ns] = rtcfg
        else:
            target = self
            keys = args
        res = target
        for key in keys:
            res = res[key]
        return res


    def adopt_orphans( self, orphans ):
        # Called by the scheduler after reloading the suite definition
        # at run time and finding any live task proxies whose
        # definitions have been removed from the suite. Keep them 
        # in the default queue and under the root family, until they
        # run their course and disappear.
        queues = self['scheduling']['queues']
        for orphan in orphans:
            self.runtime['linearized ancestors'][orphan] = [ orphan, 'root' ]
            queues['default']['members'].append( orphan )

    def configure_queues( self ):
        """ Replace family names with members, in internal queues,
         and remove assigned members from the default queue. """

        if self.verbose:
            print "Configuring internal queues"

        # NOTE: this method modifies the parsed config dict itself.

        queues = self['scheduling']['queues']
        # add all tasks to the default queue
        queues['default']['members'] = self.get_task_name_list()
        #print 'INITIAL default', queues['default']['members']
        for queue in queues:
            if queue == 'default':
                continue
            # assign tasks to queue and remove them from default
            qmembers = []
            for qmember in queues[queue]['members']:
                if qmember in self.runtime['descendants']:
                    # qmember is a family so replace it with member tasks. Note that 
                    # self.runtime['descendants'][fam] includes sub-families too.
                    for fmem in self.runtime['descendants'][qmember]:
                        if qmember not in qmembers:
                            try:
                                queues['default']['members'].remove( fmem )
                            except ValueError:
                                # no need to check for naked dummy tasks here as
                                # families are defined by runtime entries.
                                if self.verbose and fmem not in self.runtime['descendants']:
                                    # family members that are themselves families should be ignored as we only need tasks in the queues.
                                    print >> sys.stderr, '  WARNING, queue ' + queue + ': ignoring ' + fmem + ' of family ' + qmember + ' (task not used in the graph)'
                            else:
                                qmembers.append( fmem )
                else:
                    # qmember is a task
                    if qmember not in qmembers:
                        try:
                            queues['default']['members'].remove( qmember )
                        except ValueError:
                            if self.verbose:
                                print >> sys.stderr, '  WARNING, queue ' + queue + ': ignoring ' + qmember + ' (task not used in the graph)'
                            if qmember not in self['runtime']:
                                self.naked_dummy_tasks.append( qmember )
                        else:
                            qmembers.append(qmember)
            queues[queue]['members'] = qmembers
        if self.verbose:
            if len( queues.keys() ) > 1:
                for queue in queues:
                    print "  +", queue, queues[queue]['members']
            else:
                print " + All tasks assigned to the 'default' queue"

    def get_parent_lists( self ):
        return self.runtime['parents']

    def get_first_parent_ancestors( self, pruned=False ):
        if pruned:
            # prune non-task namespaces from ancestors dict
            pruned_ancestors = {}
            for key,val in self.runtime['first-parent ancestors'].items():
                if key not in self.taskdefs:
                    continue
                pruned_ancestors[key] = val
            return pruned_ancestors
        else:
            return self.runtime['first-parent ancestors']

    def get_linearized_ancestors( self ):
        return self.runtime['linearized ancestors']

    def get_first_parent_descendants( self ):
        return self.runtime['first-parent descendants']

    def define_inheritance_tree( self, tree, hierarchy, titles=False ):
        # combine inheritance hierarchies into a tree structure.
        for rt in hierarchy:
            hier = copy(hierarchy[rt])
            hier.reverse()
            foo = tree
            for item in hier:
                if item not in foo:
                    foo[item] = {}
                foo = foo[item]

    def add_tree_titles( self, tree ):
        for key,val in tree.items():
            if val == {}:
                if 'title' in self['runtime'][key]:
                    tree[key] = self['runtime'][key]['title'] 
                else:
                    tree[key] = 'No title provided'
            elif isinstance(val, dict):
                self.add_tree_titles( val )

    def get_namespace_list( self, which ):
        names = []
        if which == 'graphed tasks':
            # tasks used only in the graph
            names = self.taskdefs.keys()
        elif which == 'all namespaces':
            # all namespaces
            names = self['runtime'].keys()
        elif which == 'all tasks':
            for ns in self['runtime']:
                if ns not in self.runtime['descendants']:
                    # tasks have no descendants
                    names.append( ns )
        result = {}
        for ns in names:
            if 'title' in self['runtime'][ns]:
                # the runtime dict is sparse at this stage.
                result[ns] = self['runtime'][ns]['title']
            else:
                # no need to flesh out the full runtime just for title
                result[ns] = "No title provided"

        return result

    def get_mro( self, ns ):
        try:
            mro = self.runtime['linearized ancestors'][ns]
        except KeyError:
            mro = ["ERROR: no such namespace: " + ns ]
        return mro

    def print_first_parent_tree( self, pretty=False, titles=False ):
        # find task namespaces (no descendants)
        tasks = []
        for ns in self['runtime']:
            if ns not in self.runtime['descendants']:
                tasks.append(ns)

        pruned_ancestors = self.get_first_parent_ancestors( pruned=True )
        tree = {}
        self.define_inheritance_tree( tree, pruned_ancestors, titles=titles )
        padding = ''
        if titles:
            self.add_tree_titles(tree)
            # compute pre-title padding
            maxlen = 0
            for ns in pruned_ancestors:
                items = copy(pruned_ancestors[ns])
                items.reverse()
                for i in range(0,len(items)):
                    tmp = 2*i + 1 + len(items[i])
                    if i == 0:
                        tmp -= 1
                    if tmp > maxlen:
                        maxlen = tmp
            padding = maxlen * ' '

        print_tree( tree, padding=padding, use_unicode=pretty )

    def process_directories(self):
        os.environ['CYLC_SUITE_NAME'] = self.suite
        os.environ['CYLC_SUITE_REG_PATH'] = RegPath( self.suite ).get_fpath()
        os.environ['CYLC_SUITE_DEF_PATH'] = self.dir
        self['visualization']['runtime graph']['directory'] = expandvars( self['visualization']['runtime graph']['directory'], self.owner)

    def set_trigger( self, task_name, right, output_name=None, offset=None, asyncid_pattern=None, suicide=False ):
        trig = triggerx(task_name)
        trig.set_suicide(suicide)
        if output_name:
            try:
                # check for internal outputs
                trig.set_special( self['runtime'][task_name]['outputs'][output_name] )
            except KeyError:
                # There is no matching output defined under the task runtime section 
                if output_name == 'submit':
                    # OK, task:submit
                    trig.set_type('submitted' )
                elif output_name == 'submit-fail':
                    # OK, task:submit-fail
                    trig.set_type('submit-failed' )
                elif output_name == 'fail':
                    # OK, task:fail
                    trig.set_type('failed' )
                elif output_name == 'start':
                    # OK, task:start
                    trig.set_type('started')
                elif output_name == 'succeed':
                    # OK, task:succeed
                    trig.set_type('succeeded')
                else:
                    # ERROR
                    raise SuiteConfigError, "ERROR: '" + task_name + "' does not define output '" + output_name  + "'"
            else:
                # There is a matching output defined under the task runtime section
                if self.run_mode != 'live':
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
            print "Checking for defined tasks not used in the graph"
            for name in self['runtime']:
                if name not in self.taskdefs:
                    if name not in self.runtime['descendants']:
                        # any family triggers have have been replaced with members by now.
                        print >> sys.stderr, '  WARNING: task "' + name + '" is not used in the graph.'

        # warn if listed special tasks are not defined
        for type in self['scheduling']['special tasks']:
            for name in self['scheduling']['special tasks'][type]:
                if type == 'clock-triggered':
                    name = re.sub('\(.*\)','',name)
                if re.search( '[^0-9a-zA-Z_]', name ):
                    raise SuiteConfigError, 'ERROR: Illegal ' + type + ' task name: ' + name
                if name not in self.taskdefs and name not in self['runtime']:
                    raise SuiteConfigError, 'ERROR: special task "' + name + '" is not defined.' 
                if type == 'sequential' and name in self.runtime['descendants']:
                    raise SuiteConfigError, 'ERROR: family names cannot be declared ' + type + ': ' + name 

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
                    itask = self.taskdefs[name].get_task_class()( tag, 'waiting', None, True, validate=True )
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
                    raise
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

        # TODO - check that any multiple appearance of same task  in
        # 'special tasks' is valid. E.g. a task can be both
        # 'sequential' and 'clock-triggered' at the time, but not both
        # 'model' and 'sequential' at the same time.

    def get_filename( self ):
        return self.file

    def get_dirname( self ):
        return self.dir

    def get_coldstart_task_list( self ):
        # TODO - automatically determine this by parsing the dependency graph?
        # For now user must define this:
        return self['scheduling']['special tasks']['cold-start']

    def get_startup_task_list( self ):
        return self['scheduling']['special tasks']['start-up'] + self.async_oneoff_tasks + self.async_repeating_tasks

    def get_task_name_list( self ):
        # return a list of all tasks used in the dependency graph
        return self.taskdefs.keys()

    def get_asynchronous_task_name_list( self ):
        names = []
        for tn in self.taskdefs:
            if self.taskdefs[tn].type == 'async_repeating' or \
                    self.taskdefs[tn].type == 'async_daemon' or \
                    self.taskdefs[tn].type == 'async_oneoff':
                names.append(tn)
        return names

    def replace_family_triggers( self, line_in, fam, members, orig='' ):
        # Replace family trigger expressions with member trigger expressions.
        # The replacements below handle optional [T-n] cycle offsets.

        if orig and orig not in line_in:
            return line_in
        line = line_in
        paren_open = ''
        paren_close = ''
        connector = ' & ' 
        if orig.endswith( '-all' ):
            pass
        elif orig.endswith( '-any' ):
            connector = ' | ' 
            paren_open = '( '
            paren_close = ' )'
        elif orig != '':
            print >> sys.stderr, line
            raise SuiteConfigError, 'ERROR, illegal family trigger type: ' + orig
        repl = orig[:-4]

        m = re.findall( "(!){0,1}" + r"\b" + fam + r"\b(\[.*?]){0,1}" + orig, line )
        m.sort() # put empty offset '' first ...
        m.reverse() # ... then last
        for grp in m:
            exclam, foffset = grp 
            if fam not in self.families_used_in_graph:
                self.families_used_in_graph.append(fam)
            mems = paren_open + connector.join( [ exclam + i + foffset + repl for i in members ] ) + paren_close
            line = re.sub( exclam + r"\b" + fam + r"\b" + re.escape(foffset) + orig, mems, line )
        return line

    def process_graph_line( self, line, section ):
        # Extract dependent pairs from the suite.rc textual dependency
        # graph to use in constructing graphviz graphs.

        # 'A => B => C'    : [A => B], [B => C]
        # 'A & B => C'     : [A => C], [B => C]
        # 'A => C & D'     : [A => C], [A => D]
        # 'A & B => C & D' : [A => C], [A => D], [B => C], [B => D]

        # '&' groups aren't really "conditional expressions"; they're
        # equivalent to adding another line:
        #  'A & B => C'
        # is the same as:
        #  'A => C' and 'B => C'

        #  An 'or' on the right side is an ERROR:
        #  'A = > B | C' # ?!

        orig_line = line

        # section: [list of valid hours], or ["once"], or ["ASYNCID:pattern"]
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

        ## SYNONYMS FOR TRIGGER-TYPES, e.g. 'fail' = 'failure' = 'failed' (NOT USED)
        ## we can replace synonyms here with the standard type designator:
        # line = re.sub( r':succe(ss|ed|eded){0,1}\b', '', line )
        # line = re.sub( r':fail(ed|ure){0,1}\b', ':fail', line )
        # line = re.sub( r':start(ed){0,1}\b', ':start', line )
        # Replace "foo:finish(ed)" or "foo:complete(ed)" with "( foo | foo:fail )"
        # line = re.sub(  r'\b(\w+(\[.*?]){0,1}):(complete(d){0,1}|finish(ed){0,1})\b', r'( \1 | \1:fail )', line )

        # REPLACE FAMILY NAMES WITH MEMBER DEPENDENCIES
        for fam in self.runtime['descendants']:
            members = copy(self.runtime['descendants'][fam])
            for member in copy(members):
                # (another copy here: don't remove items from the iterating list) 
                # remove family names from the member list, leave just tasks
                # (allows using higher-level family names in the graph)
                if member in self.runtime['descendants']:
                    members.remove(member)
            # Note, in the regular expressions below, the word boundary
            # marker before the time offset pattern is required to close
            # the match in the no-offset case (offset and no-offset
            # cases are being matched by the same regular expression).

            # raw strings (r'\bfoo\b') are needed to protect special
            # backslashed re markers like \b from being interpreted as
            # normal escapeded characters.

            if fam not in line:
                continue

            # Replace family triggers with member triggers
            for trig_type in [ ':submit', ':submit-fail', ':start', ':succeed', ':fail', ':finish' ]:
                line = self.replace_family_triggers( line, fam, members, trig_type + '-all' )
                line = self.replace_family_triggers( line, fam, members, trig_type + '-any' )

            if re.search( r"\b" + fam + r"\b:", line ):
                # fam:illegal
                print >> sys.stderr, line
                raise SuiteConfigError, 'ERROR, illegal family trigger detected'

            if re.search( r"\b" + fam + r"\b[^:].*=>", line ) or re.search( r"\b" + fam + "\s*=>$", line ):
                # plain family names are not allowed on the left of a trigger
                print >> sys.stderr, line
                raise SuiteConfigError, 'ERROR, upstream family triggers must be qualified with \':type\': ' + fam

            # finally replace plain family names on the right of a trigger
            line = self.replace_family_triggers( line, fam, members )

        # any remaining use of '-all' or '-any' implies a family trigger
        # on a non-family task, which is illegal.
        if '-a' in line: # ('-' is not legal in task names so this gets both cases)
            print >> sys.stderr, line
            raise SuiteConfigError, "ERROR: family triggers cannot be used on non-family namespaces"

        # Replace "foo:finish" with "( foo:succeed | foo:fail )"
        line = re.sub(  r'\b(\w+(\[.*?]){0,1}):finish\b', r'( \1:succeed | \1:fail )', line )

        if self.verbose and line != orig_line:
            print 'Graph line substitutions occurred:'
            print '  IN:', orig_line
            print '  OUT:', line

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
               
                if not self.validation and not graphing_disabled:
                    # edges not needed for validation
                    self.generate_edges( lexpression, lnames, r, ttype, cyclr, suicide )
                self.generate_taskdefs( orig_line, lnames, r, ttype, section, cyclr, asyncid_pattern )
                self.generate_triggers( lexpression, lnames, r, cyclr, asyncid_pattern, suicide )

    def generate_edges( self, lexpression, lnames, right, ttype, cyclr, suicide=False ):
        """Add nodes from this graph section to the abstract graph edges structure."""
        conditional = False
        if re.search( '\|', lexpression ):
            # plot conditional triggers differently
            conditional = True
 
        for left in lnames:
            if left in self.async_oneoff_tasks + self.async_repeating_tasks:
                sasl = True
            else:
                sasl = False
            e = graphing.edge( left, right, cyclr, sasl, suicide, conditional )
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
                # naked dummy task, implicit inheritance from root
                self.naked_dummy_tasks.append( name )
                self['runtime'][name] = self['runtime']['root'].odict()
                if 'root' not in self.runtime['descendants']:
                    # (happens when no runtimes are defined in the suite.rc)
                    self.runtime['descendants']['root'] = []
                if 'root' not in self.runtime['first-parent descendants']:
                    # (happens when no runtimes are defined in the suite.rc)
                    self.runtime['first-parent descendants']['root'] = []
                self.runtime['parents'][name] = ['root']
                self.runtime['linearized ancestors'][name] = [name, 'root']
                self.runtime['first-parent ancestors'][name] = [name, 'root']
                self.runtime['descendants']['root'].append(name)
                self.runtime['first-parent descendants']['root'].append(name)

            if name not in self.taskdefs:
                try:
                    self.taskdefs[ name ] = self.get_taskdef( name )
                except taskdef.DefinitionError, x:
                    print >> sys.stderr, line
                    raise SuiteConfigError, str(x)

            # TODO - setting type should be consolidated to get_taskdef()
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

            if self.run_mode == 'live':
                # register any explicit internal outputs
                if 'outputs' in self['runtime'][name]:
                    for lbl,msg in self['runtime'][name]['outputs'].items():
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
                if int(lnode.offset) > int(self.taskdefs[lnode.name].intercycle_offset):
                    self.taskdefs[lnode.name].intercycle_offset = lnode.offset

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
            label = re.sub( '\+', 'x', label ) # future triggers
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
        expr = re.sub( '\+', 'x', expr ) # future triggers
        self.taskdefs[right].add_conditional_trigger( ctrig, expr, cycler )

    def get_graph_raw( self, start_ctime, stop, raw=False,
            group_nodes=[], ungroup_nodes=[], ungroup_recursive=False,
            group_all=False, ungroup_all=False ):
        """Convert the abstract graph edges held in self.edges (etc.) to
        actual edges for a concrete range of cycle times."""
        members = self.runtime['first-parent descendants']
        hierarchy = self.runtime['first-parent ancestors']
        #members = self.runtime['descendants']
        #hierarchy = self.runtime['linearized ancestors']

        if group_all:
            # Group all family nodes
            for fam in members:
                if fam != 'root':
                    if fam not in self.closed_families:
                        self.closed_families.append( fam )
        elif ungroup_all:
            # Ungroup all family nodes
            self.closed_families = []
        elif len(group_nodes) > 0:
            # Group chosen family nodes
            for node in group_nodes:
                #if node != 'root':
                    parent = hierarchy[node][1]
                    if parent not in self.closed_families:
                        if parent != 'root':
                            self.closed_families.append( parent )
        elif len(ungroup_nodes) > 0:
            # Ungroup chosen family nodes
            for node in ungroup_nodes:
                if node in self.closed_families:
                    self.closed_families.remove(node)
                if ungroup_recursive:
                    for fam in copy(self.closed_families):
                        if fam in members[node]:
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
                    # TODO - does this invalidate r_id too?
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
 
    def get_graph( self, start_ctime, stop, raw=False, group_nodes=[],
            ungroup_nodes=[], ungroup_recursive=False, group_all=False,
            ungroup_all=False, ignore_suicide=False ):

        gr_edges = self.get_graph_raw( start_ctime, stop, raw,
                group_nodes, ungroup_nodes, ungroup_recursive,
                group_all, ungroup_all )

        graph = graphing.CGraph( self.suite, self['visualization'] )
        graph.add_edges( gr_edges, ignore_suicide )

        return graph

    def close_families( self, nlid, nrid ):
        # Generate final node names, replacing family members with
        # family nodes if requested.

        # TODO - FORMATTED NODE NAMES
        # can't be used until comparison with internal IDs cope
        # for gcylc (get non-formatted tasks as disconnected nodes on
        # the right of the formatted-name base graph).
        formatted=False

        members = self.runtime['first-parent descendants']
        #members = self.runtime['descendants']

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
        clf = copy( self.closed_families )
        for i in self.closed_families:
            for j in self.closed_families:
                if i in members[j]:
                    # i is a member of j
                    if i in clf:
                        clf.remove( i )

        for fam in clf:
            if lname in members[fam] and rname in members[fam]:
                # l and r are both members of fam
                #nl, nr = None, None  # this makes 'the graph disappear if grouping 'root'
                nl,nr = fam + TaskID.DELIM +ltag, fam + TaskID.DELIM +rtag
                break
            elif lname in members[fam]:
                # l is a member of fam
                nl = fam + TaskID.DELIM + ltag
            elif rname in members[fam]:
                # r is a member of fam
                nr = fam + TaskID.DELIM + rtag

        return nl, nr

    def load_graph( self ):
        if self.verbose:
            print "Parsing the dependency graph"

        self.graph_found = False
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

        # get the task runtime
        try:
            taskcfg = self['runtime'][name]
        except KeyError:
            raise SuiteConfigError, "Task not found: " + name

        taskd = taskdef.taskdef( name, self.runtime_defaults, taskcfg, self.run_mode )

        # TODO - put all taskd.foo items in a single config dict
        # SET ONE-OFF AND COLD-START TASK INDICATORS
        if name in self['scheduling']['special tasks']['cold-start']:
            taskd.modifiers.append( 'oneoff' )
            taskd.is_coldstart = True

        if name in self['scheduling']['special tasks']['one-off'] or \
                name in self['scheduling']['special tasks']['start-up']:
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

        foo = copy(self.runtime['linearized ancestors'][ name ])
        foo.reverse()
        taskd.namespace_hierarchy = foo

        return taskd
   
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

