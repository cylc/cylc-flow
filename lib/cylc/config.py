#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re, os, sys
import traceback
from cylc.taskdef import TaskDef, TaskDefError
from cylc.cfgspec.suite import get_suitecfg
from cylc.cycling.loader import (get_point, get_point_relative,
                                 get_interval, get_interval_cls,
                                 get_sequence, get_sequence_cls,
                                 init_cyclers, INTEGER_CYCLING_TYPE,
                                 ISO8601_CYCLING_TYPE)
from cylc.cycling import IntervalParsingError
from isodatetime.data import Calendar
from envvar import check_varnames, expandvars
from copy import deepcopy, copy
from output import output
from graphnode import graphnode, GraphNodeError
from print_tree import print_tree
from prerequisites.conditionals import TriggerExpressionError
from regpath import RegPath
from trigger import trigger
from parsec.util import replicate
from cylc.task_id import TaskID
from C3MRO import C3
from parsec.OrderedDict import OrderedDict
import flags
from syntax_flags import (
    SyntaxVersion, set_syntax_version, VERSION_PREV, VERSION_NEW)
from cylc.task_proxy import TaskProxy

"""
Parse and validate the suite definition file, do some consistency
checking, then construct task proxy objects and graph structures.
"""

RE_SUITE_NAME_VAR = re.compile('\${?CYLC_SUITE_(REG_)?NAME}?')
RE_TASK_NAME_VAR = re.compile('\${?CYLC_TASK_NAME}?')
CLOCK_OFFSET_RE = re.compile(r'(' + TaskID.NAME_RE + r')(?:\(\s*(.+)\s*\))?')
NUM_RUNAHEAD_SEQ_POINTS = 5  # Number of cycle points to look at per sequence.

# TODO - unify this with task_state.py:
TRIGGER_TYPES = [ 'submit', 'submit-fail', 'start', 'succeed', 'fail', 'finish' ]
FAM_TRIGGER_TYPES = (
    [trig_type + "-any" for trig_type in TRIGGER_TYPES] +
    [trig_type + "-all" for trig_type in TRIGGER_TYPES])

# Replace \W characters in conditional graph expressions.
CONDITIONAL_REGEX_REPLACEMENTS = [
    ("\[", "_leftsquarebracket_"),
    ("\]", "_rightsquarebracket_"),
    ("-", "_minus_"),
    ("\^", "_caret_"),
    (":", "_colon_"),
    ("\+", "_plus_"),
]

try:
    import graphing
except ImportError:
    graphing_disabled = True
else:
    graphing_disabled = False


class Replacement(object):
    """A class to remember match group information in re.sub() calls"""
    def __init__(self, replacement):
        self.replacement = replacement
        self.substitutions = []
        self.match_groups = []

    def __call__(self, match):
        matched = match.group(0)
        replaced = match.expand(self.replacement)
        self.substitutions.append((matched, replaced))
        self.match_groups.append( match.groups() )
        return replaced


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

class TaskNotDefinedError(SuiteConfigError):
    """A named task not defined."""

    def __str__(self):
        return "Task not defined: %s" % self.msg

# TODO: separate config for run and non-run purposes?

class config( object ):
    def __init__(self, suite, fpath, template_vars=[], template_vars_file=None,
                 owner=None, run_mode='live', validation=False, strict=False,
                 collapsed=[], cli_initial_point_string=None,
                 cli_start_point_string=None, cli_final_point_string=None,
                 is_restart=False, is_reload=False, write_proc=True,
                 vis_start_string=None, vis_stop_string=None):

        self.suite = suite  # suite name
        self.fpath = fpath  # suite definition
        self.fdir  = os.path.dirname(fpath)
        self.owner = owner
        self.run_mode = run_mode
        self.strict = strict
        self.naked_dummy_tasks = []
        self.edges = []
        self.taskdefs = {}
        self.validation = validation
        self.initial_point = None
        self.start_point = None
        self._cli_initial_point_string = cli_initial_point_string
        self._cli_start_point_string = cli_start_point_string
        self.is_restart = is_restart
        self.first_graph = True
        self.clock_offsets = {}
        self.suite_polling_tasks = {}
        self.triggering_families = []
        self.vis_start_point_string = vis_start_string
        self.vis_stop_point_string = vis_stop_string

        self.sequences = []
        self.actual_first_point = None
        self._start_point_for_actual_first_point = None

        self.custom_runahead_limit = None
        self.max_num_active_cycle_points = None

        # runtime hierarchy dicts keyed by namespace name:
        self.runtime = {
                # lists of parent namespaces
                'parents' : {},
                # lists of C3-linearized ancestor namespaces
                'linearized ancestors' : {},
                # lists of first-parent ancestor namepaces
                'first-parent ancestors' : {},
                # lists of all descendant namespaces
                # (not including the final tasks)
                'descendants' : {},
                # lists of all descendant namespaces from the first-parent hierarchy
                # (first parents are collapsible in suite visualization)
                'first-parent descendants' : {},
                }
        # tasks
        self.leaves = []
        # one up from root
        self.feet = []

        # parse, upgrade, validate the suite, but don't expand with default items
        self.pcfg = get_suitecfg( fpath, force=is_reload,
                tvars=template_vars, tvars_file=template_vars_file,
                write_proc=write_proc )
        self.cfg = self.pcfg.get(sparse=True)

        if self._cli_initial_point_string is not None:
            self.cfg['scheduling']['initial cycle point'] = (
                self._cli_initial_point_string)

        dependency_map = self.cfg.get('scheduling', {}).get(
            'dependencies', {})

        graph_found = False
        for item, value in dependency_map.items():
            if item == 'graph':
                for line in value.split('\n'):
                    m = re.search(r"(&&)|(\|\|)", line)
                    if m:
                        linemsg = line.strip()
                        raise SuiteConfigError(
                            "ERROR: Illegal '%s' in '%s' at %s" 
                            % (m.group(0), item, linemsg)
                        )
            if item == 'graph' or value.get('graph'):
                graph_found = True
                break
        if not graph_found:
            raise SuiteConfigError('No suite dependency graph defined.')

        if 'cycling mode' not in self.cfg.get('scheduling', {}):
            # Auto-detect integer cycling for pure async graph suites.
            if dependency_map.get('graph'):
                # There is an async graph setting.
                # If it is by itself, it is integer shorthand.
                # If there are cycling graphs as well, it is handled as
                # backwards-compatiblity for mixed-async suites.
                just_has_async_graph = True
                for item, value in dependency_map.items():
                    if item != 'graph' and value.get('graph'):
                        just_has_async_graph = False
                        break
                icp = self.cfg['scheduling'].get('initial cycle point')
                fcp = self.cfg['scheduling'].get('final cycle point')
                if just_has_async_graph and not (
                        icp in [None, "1"] and fcp in [None, icp]):
                    raise SuiteConfigError('Conflicting syntax: integer vs ' +
                        'cycling suite, are you missing an [[R1]] section in' +
                        ' your graph?')
                if just_has_async_graph:
                    # There aren't any other graphs, so set integer cycling.
                    self.cfg['scheduling']['cycling mode'] = (
                        INTEGER_CYCLING_TYPE
                    )
                    if 'initial cycle point' not in self.cfg['scheduling']:
                        self.cfg['scheduling']['initial cycle point'] = "1"
                    if 'final cycle point' not in self.cfg['scheduling']:
                        self.cfg['scheduling']['final cycle point'] = "1"

        # allow test suites with no [runtime]:
        if 'runtime' not in self.cfg:
            self.cfg['runtime'] = {}

        if 'root' not in self.cfg['runtime']:
            self.cfg['runtime']['root'] = {}

        # Replace [runtime][name1,name2,...] with separate namespaces.
        if flags.verbose:
            print "Expanding [runtime] name lists"
        # This requires expansion into a new OrderedDict to preserve the
        # correct order of the final list of namespaces (add-or-override
        # by repeated namespace depends on this).
        newruntime = OrderedDict()
        for key, val in self.cfg['runtime'].items():
            if ',' in key:
                for name in re.split(' *, *', key.rstrip(', ')):
                    if name not in newruntime:
                        newruntime[name] = OrderedDict()
                    replicate(newruntime[name], val)
            else:
                if key not in newruntime:
                    newruntime[key] = OrderedDict()
                replicate(newruntime[key], val)
        self.cfg['runtime'] = newruntime
        self.ns_defn_order = newruntime.keys()

        # check var names before inheritance to avoid repetition
        self.check_env_names()

        # do sparse inheritance
        self.compute_family_tree()
        self.compute_inheritance()

        #self.print_inheritance() # (debugging)

        # filter task environment variables after inheritance
        self.filter_env()

        # now expand with defaults
        self.cfg = self.pcfg.get( sparse=False )

        # after the call to init_cyclers, we can start getting proper points.
        init_cyclers(self.cfg)

        initial_point = None
        if self.cfg['scheduling']['initial cycle point'] is not None:
            initial_point = get_point(
                self.cfg['scheduling']['initial cycle point']).standardise()
            self.cfg['scheduling']['initial cycle point'] = str(initial_point)

        self.cli_initial_point = get_point(self._cli_initial_point_string)
        if self.cli_initial_point is not None:
            self.cli_initial_point.standardise()

        self.initial_point = self.cli_initial_point or initial_point
        if self.initial_point is None:
            raise SuiteConfigError(
                "This suite requires an initial cycle point.")
        else:
            self.initial_point.standardise()

        # Validate initial cycle point against any constraints
        if self.cfg['scheduling']['initial cycle point constraints']:
            valid_icp = False
            for entry in self.cfg['scheduling']['initial cycle point constraints']:
                possible_pt = get_point_relative(entry, initial_point).standardise()
                if self.initial_point == possible_pt:
                    valid_icp = True
                    break
            if not valid_icp:
                raise SuiteConfigError(
                    "Initial cycle point %s does not meet the constraints %s"%(
                    str(self.initial_point),
                    str(self.cfg['scheduling']['initial cycle point constraints']))
                    )

        if (self.cfg['scheduling']['final cycle point'] is not None and 
            self.cfg['scheduling']['final cycle point'].strip() is ""):
                self.cfg['scheduling']['final cycle point'] = None
        final_point_string = (cli_final_point_string or
                              self.cfg['scheduling']['final cycle point'])
        final_point = None
        if final_point_string is not None:
            # Is the final "point"(/interval) relative to initial?
            if get_interval_cls().get_null().TYPE == INTEGER_CYCLING_TYPE:
                if "P" in final_point_string:
                    # Relative, integer cycling.
                    final_point = get_point_relative(
                            self.cfg['scheduling']['final cycle point'],
                        self.initial_point).standardise()
            else:
                try:
                    # Relative, ISO8601 cycling.
                    final_point = get_point_relative(
                        final_point_string, self.initial_point).standardise()
                except ValueError:
                    # (not relative)
                    pass
            if final_point is None:
                # Must be absolute.
                final_point = get_point(final_point_string).standardise()
            self.cfg['scheduling']['final cycle point'] = str(final_point)

        if final_point is not None and self.initial_point > final_point:
            raise SuiteConfigError("The initial cycle point:" +
                str(self.initial_point) + " is after the final cycle point:" +
                str(final_point) + ".")

        # Validate final cycle point against any constraints
        if (final_point is not None and
            self.cfg['scheduling']['final cycle point constraints']):
            valid_fcp = False
            for entry in self.cfg['scheduling']['final cycle point constraints']:
                possible_pt = get_point_relative(entry, final_point).standardise()
                if final_point == possible_pt:
                    valid_fcp = True
                    break
            if not valid_fcp:
                raise SuiteConfigError(
                    "Final cycle point %s does not meet the constraints %s"%(
                    str(final_point),
                    str(self.cfg['scheduling']['final cycle point constraints']))
                    )

        self.start_point = (
            get_point(self._cli_start_point_string) or self.initial_point)
        if self.start_point is not None:
            self.start_point.standardise()

        # [special tasks]: parse clock-offsets, and replace families with members
        if flags.verbose:
            print "Parsing [special tasks]"
        for type in self.cfg['scheduling']['special tasks']:
            result = copy(self.cfg['scheduling']['special tasks'][type])
            extn = ''
            for item in self.cfg['scheduling']['special tasks'][type]:
                name = item
                # Get clock-trigger offsets.
                if type == 'clock-triggered':
                    m = re.match( CLOCK_OFFSET_RE, item )
                    if m is None:
                        raise SuiteConfigError(
                            "ERROR: Illegal clock-trigger spec: %s" % item
                        )
                    if (self.cfg['scheduling']['cycling mode'] !=
                            Calendar.MODE_GREGORIAN):
                        raise SuiteConfigError(
                            "ERROR: clock-triggered tasks require " +
                            "[scheduling]cycling mode=%s" %
                            Calendar.MODE_GREGORIAN
                        )
                    name, offset_string = m.groups()
                    if not offset_string:
                        offset_string = "PT0M"
                    offset_converted_from_prev = False
                    try:
                        float(offset_string)
                    except ValueError:
                        # So the offset should be an ISO8601 interval.
                        pass
                    else:
                        # Backward-compatibility for a raw float number of hours.
                        set_syntax_version(
                            VERSION_PREV,
                            "clock-triggered=%s: integer offset" % item
                        )
                        if get_interval_cls().get_null().TYPE == ISO8601_CYCLING_TYPE:
                            seconds = int(float(offset_string)*3600)
                            offset_string = "PT%sS" % seconds
                        offset_converted_from_prev = True
                    try:
                        offset_interval = get_interval(offset_string).standardise()
                    except IntervalParsingError as exc:
                        raise SuiteConfigError(
                            "ERROR: Illegal clock-trigger spec: %s" % offset_string
                        )
                    else:
                        if not offset_converted_from_prev:
                            set_syntax_version(
                                VERSION_NEW,
                                "clock-triggered=%s: ISO 8601 offset" % item
                            )
                    extn = "(" + offset_string + ")"

                # Replace family names with members.
                if name in self.runtime['descendants']:
                    result.remove( item )
                    for member in self.runtime['descendants'][name]:
                        if member in self.runtime['descendants']:
                            # (sub-family)
                            continue
                        result.append(member + extn)
                        if type == 'clock-triggered':
                            self.clock_offsets[member] = offset_interval
                elif type == 'clock-triggered':
                    self.clock_offsets[name] = offset_interval

            self.cfg['scheduling']['special tasks'][type] = result

        self.collapsed_families_rc = self.cfg['visualization']['collapsed families']
        if is_reload:
            # on suite reload retain an existing state of collapse
            # (used by the "cylc graph" viewer)
            self.closed_families = collapsed
            fromrc = False
        else:
            self.closed_families = self.collapsed_families_rc
            fromrc = True
        for cfam in self.closed_families:
            if cfam not in self.runtime['descendants']:
                self.closed_families.remove( cfam )
                if fromrc and flags.verbose:
                    print >> sys.stderr, 'WARNING, [visualization][collapsed families]: family ' + cfam + ' not defined'

        # check for run mode override at suite level
        if self.cfg['cylc']['force run mode']:
            self.run_mode = self.cfg['cylc']['force run mode']

        self.process_directories()

        self.load_graph()

        self.compute_runahead_limits()

        self.configure_queues()

        # Warn or abort (if --strict) if naked dummy tasks (no runtime
        # section) are found in graph or queue config.
        if len( self.naked_dummy_tasks ) > 0:
            if self.strict or flags.verbose:
                print >> sys.stderr, 'WARNING: naked dummy tasks detected (no entry under [runtime]):'
                for ndt in self.naked_dummy_tasks:
                    print >> sys.stderr, '  +', ndt
            if self.strict:
                raise SuiteConfigError, 'ERROR: strict validation fails naked dummy tasks'

        if self.validation:
            self.check_tasks()

        ngs = self.cfg['visualization']['node groups']
        # If a node group member is a family, include its descendants too.
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

        if flags.verbose:
            print "Checking [visualization] node attributes"
            # 1. node groups should contain valid namespace names
            nspaces = self.cfg['runtime'].keys()
            bad = {}
            for ng,mems in ngs.items():
                n_bad = []
                for m in mems:
                    if m not in nspaces:
                        n_bad.append(m)
                if n_bad:
                    bad[ng] = n_bad
            if bad:
                print >> sys.stderr, "  WARNING: undefined node group members"
                for ng,mems in bad.items():
                    print >> sys.stderr, " + " + ng + ":", ','.join(mems)

            # 2. node attributes must refer to node groups or namespaces
            bad = []
            for na in self.cfg['visualization']['node attributes']:
                if na not in ngs and na not in nspaces:
                    bad.append(na)
            if bad:
                print >> sys.stderr, "  WARNING: undefined node attribute targets"
                for na in bad:
                    print >> sys.stderr, " + " + na

        # (Note that we're retaining 'default node attributes' even
        # though this could now be achieved by styling the root family,
        # because putting default attributes for root in the suite.rc spec
        # results in root appearing last in the ordered dict of node
        # names, so it overrides the styling for lesser groups and
        # nodes, whereas the reverse is needed - fixing this would
        # require reordering task_attr in lib/cylc/graphing.py).

        self.leaves = self.get_task_name_list()
        for ns, ancestors in self.runtime['first-parent ancestors'].items():
            try:
                foot = ancestors[-2] # one back from 'root'
            except IndexError:
                pass
            else:
                if foot not in self.feet:
                    self.feet.append(foot)

        # CLI override for visualization settings.
        if self.vis_start_point_string:
            self.cfg['visualization']['initial cycle point'] = self.vis_start_point_string
        if self.vis_stop_point_string:
            self.cfg['visualization']['final cycle point'] = self.vis_stop_point_string

        # For static visualization, start point defaults to suite initial
        # point; stop point must be explicit with initial point, or None.
        if self.cfg['visualization']['initial cycle point'] is None:
            self.cfg['visualization']['initial cycle point'] = (
                    self.cfg['scheduling']['initial cycle point'])
            # If viz initial point is None don't accept a final point.
            if self.cfg['visualization']['final cycle point'] is not None:
                if flags.verbose:
                    print >> sys.stderr, (
                        "WARNING: ignoring [visualization]final cycle point\n"
                        "  (it must be defined with an initial cycle point)")
                self.cfg['visualization']['final cycle point'] = None


        vfcp = self.cfg['visualization']['final cycle point']
        if vfcp:
            try:
                vfcp = get_point_relative(
                    self.cfg['visualization']['final cycle point'],
                    initial_point).standardise()
            except ValueError:
                vfcp = get_point(
                    self.cfg['visualization']['final cycle point']).standardise()

        if vfcp is not None and final_point is not None:
            if vfcp > final_point:
                self.cfg['visualization']['final cycle point'] = str(final_point)

        # Replace suite name in suite  URL.
        url = self.cfg['URL']
        if url is not '':
            self.cfg['URL'] = re.sub(RE_SUITE_NAME_VAR, self.suite, url)

        # Replace suite and task name in task URLs.
        for name, cfg in self.cfg['runtime'].items():
            if cfg['URL']:
                cfg['URL'] = re.sub(RE_TASK_NAME_VAR, name, cfg['URL'])
                cfg['URL'] = re.sub(RE_SUITE_NAME_VAR, self.suite, cfg['URL'])

    def check_env_names( self ):
        # check for illegal environment variable names
         bad = {}
         for label in self.cfg['runtime']:
             res = []
             if 'environment' in self.cfg['runtime'][label]:
                 res = check_varnames( self.cfg['runtime'][label]['environment'] )
             if res:
                 bad[label] = res
         if bad:
             print >> sys.stderr, "ERROR, bad env variable names:"
             for label, vars in bad.items():
                 print >> sys.stderr, 'Namespace:', label
                 for var in vars:
                     print >> sys.stderr, "  ", var
             raise SuiteConfigError("Illegal env variable name(s) detected" )

    def filter_env( self ):
        # filter environment variables after sparse inheritance
        for name, ns in self.cfg['runtime'].items():
            try:
                oenv = ns['environment']
            except KeyError:
                # no environment to filter
                continue

            try:
                fincl = ns['environment filter']['include']
            except KeyError:
                # empty include-filter means include all
                fincl = []

            try:
                fexcl = ns['environment filter']['exclude']
            except KeyError:
                # empty exclude-filter means exclude none
                fexcl = []

            if not fincl and not fexcl:
                # no filtering to do
                continue

            nenv = OrderedDict()
            for key, val in oenv.items():
                if ( not fincl or key in fincl ) and key not in fexcl:
                    nenv[key] = val
            ns['environment'] = nenv

    def compute_family_tree( self ):
        first_parents = {}
        demoted = {}
        for name in self.cfg['runtime']:
            if name == 'root':
                self.runtime['parents'][name] = []
                first_parents[name] = []
                continue
            # get declared parents, with implicit inheritance from root.
            pts = self.cfg['runtime'][name].get( 'inherit', ['root'] )
            for p in pts:
                if p == "None":
                    # see just below
                    continue
                if p not in self.cfg['runtime']:
                    raise SuiteConfigError, "ERROR, undefined parent for " + name +": " + p
            if pts[0] == "None":
                if len(pts) == 1:
                    raise SuiteConfigError, "ERROR: null parentage for " + name
                demoted[name] = pts[1]
                pts = pts[1:]
                first_parents[name] = ['root']
            else:
                first_parents[name] = [ pts[0] ]
            self.runtime['parents'][name] = pts

        if flags.verbose and demoted:
            print "First parent(s) demoted to secondary:"
            for n,p in demoted.items():
                print " +", p, "as parent of '" + n + "'"

        c3 = C3( self.runtime['parents'] )
        c3_single = C3( first_parents )

        for name in self.cfg['runtime']:
            try:
                self.runtime['linearized ancestors'][name] = c3.mro(name)
                self.runtime['first-parent ancestors'][name] = c3_single.mro(name)
            except RuntimeError as exc:
                if flags.debug:
                    raise
                exc_lines =  traceback.format_exc().splitlines()
                if exc_lines[-1].startswith(
                    "RuntimeError: maximum recursion depth exceeded"):
                    sys.stderr.write("ERROR: circular [runtime] inheritance?\n")
                else:
                    sys.stderr.write("ERROR: %s\n" % str(exc))
                sys.exit(1)

        for name in self.cfg['runtime']:
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

        #for name in self.cfg['runtime']:
        #    print name, self.runtime['linearized ancestors'][name]

    def compute_inheritance( self, use_simple_method=True ):
        if flags.verbose:
            print "Parsing the runtime namespace hierarchy"

        results = {}
        n_reps = 0

        already_done = {} # to store already computed namespaces by mro

        for ns in self.cfg['runtime']:
            # for each namespace ...

            hierarchy = copy(self.runtime['linearized ancestors'][ns])
            hierarchy.reverse()

            result = {}

            if use_simple_method:
                # Go up the linearized MRO from root, replicating or
                # overriding each namespace element as we go.
                for name in hierarchy:
                    replicate( result, self.cfg['runtime'][name] )
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
                            result = {}
                            replicate(result,ad_result) # ...and use stored
                            n_reps += 1
                        # override name content into tmp
                        replicate( result, self.cfg['runtime'][name] )
                        n_reps += 1
                        # record this mro as already done
                        already_done[i_mro] = result

            results[ns] = result

        # replace pre-inheritance namespaces with the post-inheritance result
        self.cfg['runtime'] = results

        # uncomment this to compare the simple and efficient methods
        # print '  Number of namespace replications:', n_reps

    def print_inheritance(self):
        # (use for debugging)
        for foo in self.runtime:
            print '  ', foo
            for item, val in self.runtime[foo].items():
                print '  ', '  ', item, val

    def compute_runahead_limits( self ):
        """Extract the runahead limits information."""
        max_cycles = self.cfg['scheduling']['max active cycle points']
        if max_cycles == 0:
            raise SuiteConfigError(
                "ERROR: max cycle points must be greater than %s"
                 % (max_cycles)
            )
        self.max_num_active_cycle_points = self.cfg['scheduling'][
            'max active cycle points']

        limit = self.cfg['scheduling']['runahead limit']
        if (limit is not None and limit.isdigit() and
                get_interval_cls().get_null().TYPE == ISO8601_CYCLING_TYPE):
            # Backwards-compatibility for raw number of hours.
            limit = "PT%sH" % limit

        # The custom runahead limit is None if not user-configured.
        self.custom_runahead_limit = get_interval(limit)

    def get_custom_runahead_limit( self ):
        """Return the custom runahead limit (may be None)."""
        return self.custom_runahead_limit

    def get_max_num_active_cycle_points( self ):
        """Return the maximum allowed number of pool cycle points."""
        return self.max_num_active_cycle_points

    def get_config( self, args, sparse=False ):
        return self.pcfg.get( args, sparse )

    def adopt_orphans( self, orphans ):
        # Called by the scheduler after reloading the suite definition
        # at run time and finding any live task proxies whose
        # definitions have been removed from the suite. Keep them
        # in the default queue and under the root family, until they
        # run their course and disappear.
        queues = self.cfg['scheduling']['queues']
        for orphan in orphans:
            self.runtime['linearized ancestors'][orphan] = [ orphan, 'root' ]
            queues['default']['members'].append( orphan )

    def configure_queues( self ):
        """Assign tasks to internal queues."""
        # Note this modifies the parsed config dict.
        queues = self.cfg['scheduling']['queues']

        if flags.verbose:
            print "Configuring internal queues"

        # First add all tasks to the default queue.
        all_task_names = self.get_task_name_list()
        queues['default']['members'] = all_task_names

        # Then reassign to other queues as requested.
        warnings = []
        requeued = []
        for queue in queues:
            if queue == 'default':
                continue
            # Assign tasks to queue and remove them from default.
            qmembers = []
            for qmember in queues[queue]['members']:
                # Is a family.
                if qmember in self.runtime['descendants']:
                    # Replace with member tasks.
                    for fmem in self.runtime['descendants'][qmember]:
                        # This includes sub-families.
                        if qmember not in qmembers:
                            try:
                                queues['default']['members'].remove(fmem)
                            except ValueError:
                                if fmem in requeued:
                                    msg = "%s: ignoring %s from %s (already assigned to a queue)" % (
                                            queue, fmem, qmember)
                                    warnings.append(msg)
                                else:
                                    # Ignore: task not used in the graph.
                                    pass
                            else:
                                qmembers.append(fmem)
                                requeued.append(fmem)
                else:
                    # Is a task.
                    if qmember not in qmembers:
                        try:
                            queues['default']['members'].remove(qmember)
                        except ValueError:
                            if qmember in requeued:
                                msg = "%s: ignoring '%s' (task already assigned)" % (
                                        queue, qmember)
                                warnings.append(msg)
                            elif qmember not in all_task_names:
                                msg = "%s: ignoring '%s' (task not defined)" % (
                                        queue, qmember)
                                warnings.append(msg)
                            else:
                                # Ignore: task not used in the graph.
                                pass
                        else:
                            qmembers.append(qmember)
                            requeued.append(qmember)

            if len(warnings) > 0:
                print >> sys.stderr, "Queue configuration WARNINGS:"
                for msg in warnings:
                    print >> sys.stderr, " + %s" % msg

            if len(qmembers) > 0:
                queues[queue]['members'] = qmembers
            else:
                del queues[queue]

        if flags.verbose and len(queues.keys()) > 1:
            print "Internal queues created:"
            for queue in queues:
                if queue == 'default':
                    continue
                print "  + %s: %s" % (
                        queue, ', '.join(queues[queue]['members']))

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
                if 'title' in self.cfg['runtime'][key]:
                    tree[key] = self.cfg['runtime'][key]['title']
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
            names = self.cfg['runtime'].keys()
        elif which == 'all tasks':
            for ns in self.cfg['runtime']:
                if ns not in self.runtime['descendants']:
                    # tasks have no descendants
                    names.append( ns )
        result = {}
        for ns in names:
            if 'title' in self.cfg['runtime'][ns]:
                # the runtime dict is sparse at this stage.
                result[ns] = self.cfg['runtime'][ns]['title']
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
        for ns in self.cfg['runtime']:
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
        os.environ['CYLC_SUITE_DEF_PATH'] = self.fdir

    def check_tasks( self ):
        # Call after all tasks are defined.
        # ONLY IF VALIDATING THE SUITE
        # because checking conditional triggers below may be slow for
        # huge suites (several thousand tasks).
        # Note:
        #   (a) self.cfg['runtime'][name]
        #       contains the task definition sections of the suite.rc file.
        #   (b) self.taskdefs[name]
        #       contains tasks that will be used, defined by the graph.
        # Tasks (a) may be defined but not used (e.g. commented out of the graph)
        # Tasks (b) may not be defined in (a), in which case they are dummied out.

        for taskdef in self.taskdefs.values():
            try:
                taskdef.check_for_explicit_cycling()
            except TaskDefError as exc:
                raise SuiteConfigError(str(exc))
 
        if flags.verbose:
            print "Checking for defined tasks not used in the graph"
            for name in self.cfg['runtime']:
                if name not in self.taskdefs:
                    if name not in self.runtime['descendants']:
                        # any family triggers have have been replaced with members by now.
                        print >> sys.stderr, '  WARNING: task "' + name + '" is not used in the graph.'

        # warn if listed special tasks are not defined
        for type in self.cfg['scheduling']['special tasks']:
            for name in self.cfg['scheduling']['special tasks'][type]:
                if type == 'clock-triggered':
                    name = re.sub('\(.*\)','',name)
                if re.search( '[^0-9a-zA-Z_]', name ):
                    raise SuiteConfigError, 'ERROR: Illegal ' + type + ' task name: ' + name
                if name not in self.taskdefs and name not in self.cfg['runtime']:
                    raise SuiteConfigError, 'ERROR: special task "' + name + '" is not defined.'

        try:
            import Pyro.constants
        except:
            print >> sys.stderr, "WARNING, INCOMPLETE VALIDATION: Pyro is not installed"
            return

        # Instantiate tasks and force evaluation of trigger expressions.
        # TODO - This is not exhaustive, it only uses the initial cycle point.
        if flags.verbose:
            print "Instantiating tasks to check trigger expressions"
        for name in self.taskdefs.keys():
            try:
                itask = TaskProxy(
                    self.taskdefs[name],
                    self.start_point,
                    'waiting',
                    is_startup=True,
                    validate_mode=True)
            except Exception, x:
                raise SuiteConfigError(
                    'ERROR, failed to instantiate task %s: %s' % (name, x))
            if itask.point is None:
                if flags.verbose:
                    print " + Task out of bounds for " + str(self.start_point) + ": " + itask.name
                continue

            # warn for purely-implicit-cycling tasks (these are deprecated).
            if itask.tdef.sequences == itask.tdef.implicit_sequences:
                print >> sys.stderr, (
                    "WARNING, " + name + ": not explicitly defined in " +
                    "dependency graphs (deprecated)"
                )

            # force trigger evaluation now
            try:
                itask.prerequisites.eval_all()
            except TriggerExpressionError, x:
                print >> sys.stderr, x
                raise SuiteConfigError, "ERROR, " + name + ": invalid trigger expression."
            except Exception, x:
                print >> sys.stderr, x
                raise SuiteConfigError, 'ERROR, ' + name + ': failed to evaluate triggers.'
            if flags.verbose:
                print "  + " + itask.identity + " ok"

        # Check custom script is not defined for automatic suite polling tasks
        for l_task in self.suite_polling_tasks:
            try:
                cs = self.pcfg.getcfg( sparse=True )['runtime'][l_task]['script']
            except:
                pass
            else:
                if cs:
                    print cs
                    # (allow explicit blanking of inherited script)
                    raise SuiteConfigError( "ERROR: script cannot be defined for automatic suite polling task " + l_task )


    def get_coldstart_task_list( self ):
        return self.cfg['scheduling']['special tasks']['cold-start']

    def get_task_name_list( self ):
        # return a list of all tasks used in the dependency graph
        return self.taskdefs.keys()

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

        # TODO - can we use Replacement here instead of findall and sub:
        m = re.findall( "(!){0,1}" + r"\b" + fam + r"\b(\[.*?]){0,1}" + orig, line )
        m.sort() # put empty offset '' first ...
        m.reverse() # ... then last
        for grp in m:
            exclam, foffset = grp
            if fam not in self.triggering_families:
                self.triggering_families.append(fam)
            mems = paren_open + connector.join( [ exclam + i + foffset + repl for i in members ] ) + paren_close
            line = re.sub( exclam + r"\b" + fam + r"\b" + re.escape(foffset) + orig, mems, line )
        return line

    def process_graph_line( self, line, section, seq, offset_seq_map,
                            tasks_to_prune=None,
                            return_all_dependencies=False ):
        """Extract dependent pairs from the suite.rc dependency text.

        Extract dependent pairs from the suite.rc textual dependency
        graph to use in constructing graphviz graphs.

        Return a list of dependencies involving 'start-up' tasks
        (backwards compatibility) or all dependencies if
        return_all_dependencies keyword argument is True.

        line is the line of text within the 'graph' attribute of
        this dependency section.
        section is the text describing this dependency section (e.g.
        T00).
        seq is the sequence generated from 'section' given the initial
        and final cycle point.
        offset_seq_map is a cache of seq with various offsets for
        speeding up backwards-compatible cycling.
        tasks_to_prune, if not None, is a list of tasks to remove
        from dependency expressions (backwards compatibility for
        start-up tasks and async graph tasks).
        return_all_dependencies, if True, indicates that all
        dependencies between tasks in this graph should be returned.
        Otherwise, just return tasks_to_prune dependencies, if any.

        'A => B => C'    : [A => B], [B => C]
        'A & B => C'     : [A => C], [B => C]
        'A => C & D'     : [A => C], [A => D]
        'A & B => C & D' : [A => C], [A => D], [B => C], [B => D]

        '&' groups aren't really "conditional expressions"; they're
        equivalent to adding another line:
        'A & B => C'
        is the same as:
        'A => C' and 'B => C'

        An 'or' on the right side is an ERROR:
        'A = > B | C' # ?!

        """

        if tasks_to_prune is None:
            tasks_to_prune = []

        orig_line = line

        base_interval = seq.get_interval()

        ## SYNONYMS FOR TRIGGER-TYPES, e.g. 'fail' = 'failure' = 'failed' (NOT USED)
        ## we can replace synonyms here with the standard type designator:
        # line = re.sub( r':succe(ss|ed|eded){0,1}\b', '', line )
        # line = re.sub( r':fail(ed|ure){0,1}\b', ':fail', line )
        # line = re.sub( r':start(ed){0,1}\b', ':start', line )
        # Replace "foo:finish(ed)" or "foo:complete(ed)" with "( foo | foo:fail )"
        # line = re.sub(  r'\b(\w+(\[.*?]){0,1}):(complete(d){0,1}|finish(ed){0,1})\b', r'( \1 | \1:fail )', line )

        # Find any dependence on other suites, record the polling target
        # info and replace with just the local task name, e.g.:
        # "foo<SUITE::TASK:fail> => bar"  becomes "foo => bar"
        # (and record that foo must automatically poll for TASK in SUITE)
        repl = Replacement( '\\1' )
        line = re.sub( '(\w+)(<([\w\.\-]+)::(\w+)(:\w+)?>)', repl, line )
        for item in repl.match_groups:
            l_task, r_all, r_suite, r_task, r_status = item
            if r_status:
                r_status = r_status[1:]
            else: # default
                r_status = 'succeed'
            self.suite_polling_tasks[ l_task ] = ( r_suite, r_task, r_status, r_all )

        # REPLACE FAMILY NAMES WITH MEMBER DEPENDENCIES
        # Sort so that longer family names get expanded first.
        # This expands e.g. FOO-BAR before FOO in FOO-BAR:succeed-all => baz.
        for fam in reversed(sorted(self.runtime['descendants'])):
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
            for trig_type in FAM_TRIGGER_TYPES:
                line = self.replace_family_triggers(
                    line, fam, members, ':' + trig_type)

            if re.search( r"\b" + fam + r"\b:", line ):
                # fam:illegal
                print >> sys.stderr, line
                raise SuiteConfigError, 'ERROR, illegal family trigger detected'

            if re.search( r"\b" + fam + r"\b[^:].*=>", line ) or re.search( r"\b" + fam + "\s*=>$", line ):
                # plain family names are not allowed on the left of a trigger
                print >> sys.stderr, line
                raise SuiteConfigError, 'ERROR, family triggers must be qualified, e.g. ' + fam + ':succeed-all'

            # finally replace plain family names on the right of a trigger
            line = self.replace_family_triggers( line, fam, members )

        # any remaining use of '-all' or '-any' implies a family trigger
        # on a non-family task, which is illegal.
        if any([":" + trig_type in line for trig_type in FAM_TRIGGER_TYPES]):
            print >> sys.stderr, line
            raise SuiteConfigError, "ERROR: family triggers cannot be used on non-family namespaces"

        # Replace "foo:finish" with "( foo:succeed | foo:fail )"
        line = re.sub(  r'\b(\w+(\[.*?]){0,1}):finish\b', r'( \1:succeed | \1:fail )', line )

        if flags.verbose and line != orig_line:
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
        special_dependencies = []
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
                if re.search( '\[\s*T\s*[+-]\s*\w+\s*\]', rgroup ):
                    print >> sys.stderr, orig_line
                    raise SuiteConfigError, "ERROR: time offsets are not legal on the right side of dependencies: " + rgroup

                # now split on '&' (AND) and generate corresponding pairs
                right_nodes = re.split( '\s*&\s*', rgroup )
            else:
                right_nodes = [None]

            new_right_nodes = []
            for right_node in right_nodes:
                if right_node:
                    # ignore output labels on the right (for chained
                    # tasks they are only meaningful on the left)
                    new_right_nodes.append( re.sub( ':\w+', '', right_node ))
                else:
                    # retain None's in order to handle lone nodes on the left
                    new_right_nodes.append( None )

            right_nodes = new_right_nodes

            # extract task names from lexpression
            n_open_brackets = len(re.findall(r"(\()", lexpression))
            n_close_brackets = len(re.findall(r"(\))", lexpression))
            if n_open_brackets != n_close_brackets:
                raise SuiteConfigError, (
                    "ERROR: missing bracket in: \"" + lexpression + "\"") 
            nstr = re.sub( '[(|&)]', ' ', lexpression )
            nstr = nstr.strip()
            left_nodes = re.split( ' +', nstr )

            # detect and fail and self-dependence loops (foo => foo)
            for right_node in right_nodes:
                if right_node in left_nodes:
                    print >> sys.stderr, (
                        "Self-dependence detected in '" + right_node + "':")
                    print >> sys.stderr, "  line:", line
                    print >> sys.stderr, "  from:", orig_line
                    raise SuiteConfigError, "ERROR: self-dependence loop detected"

            for right_node in right_nodes:
                # foo => '!bar' means task bar should suicide if foo succeeds.
                suicide = False
                if right_node and right_node.startswith('!'):
                    right_name = right_node[1:]
                    suicide = True
                else:
                    right_name = right_node

                pruned_left_nodes = list(left_nodes)  # Create copy of LHS tasks.

                for left_node in left_nodes:
                    try:
                        left_graph_node = graphnode(left_node, base_interval)
                    except GraphNodeError, x:
                        print >> sys.stderr, orig_line
                        raise SuiteConfigError, str(x)
                    left_name = left_graph_node.name
                    left_output = left_graph_node.output
                    if (left_name in tasks_to_prune or
                            return_all_dependencies or
                            right_name in tasks_to_prune):
                        special_dep = (left_name, left_output, right_name)
                        if (left_name + ":finish" in orig_line and
                                left_output in ["succeed", "fail"]):
                            # Handle 'finish' explicitly to avoid OR cases.
                            special_dep = (left_name, "finish", right_name)
                            if special_dep not in special_dependencies:
                                # Avoid repeating for succeed and fail.
                                special_dependencies.append(special_dep)
                        else:
                            special_dependencies.append(special_dep)
                    if left_name in tasks_to_prune:
                        pruned_left_nodes.remove(left_node)

                if right_name in tasks_to_prune:
                    continue

                if not self.validation and not graphing_disabled:
                    # edges not needed for validation
                    left_edge_nodes = pruned_left_nodes
                    right_edge_node = right_name
                    if not left_edge_nodes and left_nodes:
                        # All the left nodes have been pruned.
                        left_edge_nodes = [right_name]
                        right_edge_node = None
                    self.generate_edges(lexpression, left_edge_nodes,
                                        right_edge_node, seq, suicide)
                self.generate_taskdefs(orig_line, pruned_left_nodes,
                                        right_name, section,
                                        seq, offset_seq_map,
                                        base_interval)
                self.generate_triggers(lexpression, pruned_left_nodes,
                                        right_name, seq, suicide)
        return special_dependencies


    def generate_edges( self, lexpression, left_nodes, right, seq, suicide=False ):
        """Add nodes from this graph section to the abstract graph edges structure."""
        conditional = False
        if re.search( '\|', lexpression ):
            # plot conditional triggers differently
            conditional = True

        for left in left_nodes:
            if left is not None:
                e = graphing.edge( left, right, seq, suicide, conditional )
                self.edges.append(e)

    def generate_taskdefs( self, line, left_nodes, right, section, seq,
                           offset_seq_map, base_interval ):
        """Generate task definitions for nodes on a given line."""
        for node in left_nodes + [right]:
            if not node:
                # if right is None, lefts are lone nodes
                # for which we still define the taskdefs
                continue
            try:
                my_taskdef_node = graphnode( node, base_interval=base_interval )
            except GraphNodeError, x:
                print >> sys.stderr, line
                raise SuiteConfigError, str(x)

            name = my_taskdef_node.name
            offset_string = my_taskdef_node.offset_string

            if name not in self.cfg['runtime']:
                # naked dummy task, implicit inheritance from root
                self.naked_dummy_tasks.append( name )
                # These can't just be a reference to root runtime as we have to
                # make some items task-specific: e.g. subst task name in URLs.
                self.cfg['runtime'][name] = OrderedDict()
                replicate(self.cfg['runtime'][name], self.cfg['runtime']['root'])
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
                self.ns_defn_order.append(name)

            # check task name legality and create the taskdef
            if name not in self.taskdefs:
                try:
                    self.taskdefs[ name ] = self.get_taskdef( name )
                except TaskDefError as exc:
                    print >> sys.stderr, line
                    raise SuiteConfigError(str(exc))

            if name in self.suite_polling_tasks:
                self.taskdefs[name].suite_polling_cfg = {
                        'suite'  : self.suite_polling_tasks[name][0],
                        'task'   : self.suite_polling_tasks[name][1],
                        'status' : self.suite_polling_tasks[name][2] }

            if not my_taskdef_node.is_absolute:
                if offset_string:
                    self.taskdefs[name].used_in_offset_trigger = True
                    if SyntaxVersion.VERSION == VERSION_PREV:
                        # Implicit cycling means foo[T+6] generates a +6 sequence.
                        if offset_string in offset_seq_map:
                            seq_offset = offset_seq_map[offset_string]
                        else:
                            seq_offset = get_sequence(
                                section,
                                self.cfg['scheduling']['initial cycle point'],
                                self.cfg['scheduling']['final cycle point']
                            )
                            seq_offset.set_offset(
                                get_interval(offset_string))
                            offset_seq_map[offset_string] = seq_offset
                        self.taskdefs[name].add_sequence(
                            seq_offset, is_implicit=True)
                        if seq_offset not in self.sequences:
                            self.sequences.append(seq_offset)
                    # We don't handle implicit cycling in new-style cycling.
                else:
                    self.taskdefs[ name ].add_sequence(seq)

            if self.run_mode == 'live':
                # register any explicit internal outputs
                if 'outputs' in self.cfg['runtime'][name]:
                    for lbl,msg in self.cfg['runtime'][name]['outputs'].items():
                        outp = output(msg, base_interval)
                        self.taskdefs[name].outputs.append(outp)

    def generate_triggers( self, lexpression, left_nodes, right, seq, suicide ):
        if not right:
            # lefts are lone nodes; no more triggers to define.
            return
        
        if not left_nodes:
            # Nothing actually remains to trigger right.
            return

        base_interval = seq.get_interval()

        conditional = False
        if re.search( '\|', lexpression ):
            conditional = True
            # For single triggers or '&'-only ones, which will be the
            # vast majority, we needn't use conditional prerequisites
            # (they may be less efficient due to python eval at run time).

        ctrig = {}
        cname = {}
        for left in left_nodes:
            # (GraphNodeError checked above)
            cycle_point = None
            lnode = graphnode(left, base_interval=base_interval)
            ltaskdef = self.taskdefs[lnode.name]

            if lnode.offset_is_from_ict:
                first_point = get_point_relative(
                    lnode.offset_string, self.initial_point)
                last_point = seq.get_stop_point()
                if last_point is None:
                    # This dependency persists for the whole suite run.
                    ltaskdef.intercycle_offsets.append(
                        (None, seq))
                else:
                    ltaskdef.intercycle_offsets.append(
                        (str(-(last_point - first_point)), seq))
                cycle_point = first_point
            elif lnode.intercycle:
                if lnode.offset_is_irregular:
                    offset_tuple = (lnode.offset_string, seq)
                else:
                    offset_tuple = (lnode.offset_string, None)
                ltaskdef.intercycle_offsets.append(offset_tuple)

            trig = trigger(
                    lnode.name, lnode.output, lnode.offset_string,
                    cycle_point, suicide,
                    self.cfg['runtime'][lnode.name]['outputs'],
                    base_interval
            )

            if self.run_mode != 'live' and not trig.is_standard():
                # Dummy tasks do not report message outputs.
                continue

            if not conditional:
                self.taskdefs[right].add_trigger( trig, seq )
                continue

            # CONDITIONAL TRIGGERS
            # Use fully qualified name for the expression label
            # (task name is not unique, e.g.: "F | F:fail => G")
            label = self.get_conditional_label(left)
            ctrig[label] = trig
            cname[label] = lnode.name

        if not conditional:
            return

        expr = self.get_conditional_label(lexpression)
        self.taskdefs[right].add_conditional_trigger( ctrig, expr, seq )

    def get_actual_first_point( self, start_point ):
        # Get actual first cycle point for the suite (get all
        # sequences to adjust the putative start time upward)
        if (self._start_point_for_actual_first_point is not None and
                self._start_point_for_actual_first_point == start_point and
                self.actual_first_point is not None):
            return self.actual_first_point
        self._start_point_for_actual_first_point = start_point
        adjusted = []
        for seq in self.sequences:
            foo = seq.get_first_point( start_point )
            if foo:
                adjusted.append( foo )
        if len( adjusted ) > 0:
            adjusted.sort()
            self.actual_first_point = adjusted[0]
        else:
            self.actual_first_point = start_point
        return self.actual_first_point

    def get_conditional_label( self, expression ):
        """Return a label to ID the expression.

        Special characters such as [, or ^ are replaced with
        nice \w+ text for use in regular expressions and trigger
        task matching. We don't back-transform the label, so
        all it needs to is provide locally unique IDs for the
        bits of the trigger.

        For example, "foo[^] | bar" is represented in text as
        "foo_leftsquarebracket__caret__rightsquarebracket_ | bar".
        As long as no one uses that exact "foo_leftsquare...." text as
        a task name as part of a conditional trigger for the *same*
        task, we're OK.

        Should we use unicodedata.name to convert the character names,
        and support much more characters in the task names?

        """
        label = expression
        for regex, replacement in CONDITIONAL_REGEX_REPLACEMENTS:
            label = re.sub(regex, replacement, label)
        return label

    def get_graph_raw( self, start_point_string, stop_point_string,
            group_nodes=[], ungroup_nodes=[], ungroup_recursive=False,
            group_all=False, ungroup_all=False ):
        """Convert the abstract graph edges held in self.edges (etc.) to
        actual edges for a concrete range of cycle points."""

        members = self.runtime['first-parent descendants']
        hierarchy = self.runtime['first-parent ancestors']

        if self.first_graph:
            self.first_graph = False
            if not self.collapsed_families_rc and not ungroup_all:
                # initially default to collapsing all families if
                # "[visualization]collapsed families" not defined
                group_all = True

        if group_all:
            # Group all family nodes
            if self.collapsed_families_rc:
                self.closed_families = copy(self.collapsed_families_rc)
            else:
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
                parent = hierarchy[node][1]
                if parent not in self.closed_families:
                    if parent != 'root':
                        self.closed_families.append( parent )
        elif len(ungroup_nodes) > 0:
            # Ungroup chosen family nodes
            for node in ungroup_nodes:
                if node not in self.runtime['descendants']:
                    # not a family node
                    continue
                if node in self.closed_families:
                    self.closed_families.remove(node)
                if ungroup_recursive:
                    for fam in copy(self.closed_families):
                        if fam in members[node]:
                            self.closed_families.remove(fam)

        # Now define the concrete graph edges (pairs of nodes) for plotting.
        gr_edges = {}
        start_point = get_point(start_point_string)
        actual_first_point = self.get_actual_first_point(start_point)

        # For the computed stop point, we store n_points of each sequence,
        # and then cull later to the first n_points over all sequences.
        n_points = self.cfg['visualization']['number of cycle points']
        if stop_point_string is not None:
            stop_point = get_point(stop_point_string)
        else:
            stop_point = None

        for e in self.edges:
            # Get initial cycle point for this sequence
            i_point = e.sequence.get_first_point(start_point)
            if i_point is None:
                # out of bounds
                continue
            point = deepcopy(i_point)
            new_points = []
            while True:
                # Loop over cycles generated by this sequence
                if point is None:
                    # Out of sequence bounds.
                    break
                if point not in new_points:
                    new_points.append(point)
                if stop_point is not None and point > stop_point:
                    # Beyond requested final cycle point.
                    break
                if stop_point is None and len(new_points) > n_points:
                    # Take n_points cycles from each sequence.
                    break
                not_initial_cycle = (point != i_point)

                r_id = e.get_right(point, start_point)
                l_id = e.get_left(point, start_point, e.sequence.get_interval())

                action = True
                if l_id == None and r_id == None:
                    # Nothing to add to the graph.
                    action = False
                if l_id != None:
                    # Check that l_id is not earlier than start time.
                    tmp, lpoint_string = TaskID.split(l_id)
                    ## NOTE BUG GITHUB #919
                    ##sct = start_point
                    sct = actual_first_point
                    lct = get_point(lpoint_string)
                    if sct > lct:
                        action = False
                        if r_id is not None:
                            tmp, rpoint_string = TaskID.split(r_id)
                            rct = get_point(rpoint_string)
                            if rct >= sct:
                                # Pre-initial dependency; keep right hand node.
                                l_id = r_id
                                r_id = None
                                action = True
                if action:
                    nl, nr = self.close_families(l_id, r_id)
                    if point not in gr_edges:
                        gr_edges[point] = []
                    gr_edges[point].append((nl, nr, False, e.suicide, e.conditional))
                # Increment the cycle point.
                point = e.sequence.get_next_point_on_sequence(point)

        edges = []
        if stop_point is None:
            # Prune to n_points points in total.
            points = gr_edges.keys()
            for point in sorted(points)[:n_points]:
                edges.extend(gr_edges[point])
        else:
            values = gr_edges.values()
            # Flatten nested list.
            edges = [i for sublist in values for i in sublist]

        return edges

    def get_graph(self, start_point_string=None, stop_point_string=None,
            group_nodes=[], ungroup_nodes=[], ungroup_recursive=False,
            group_all=False, ungroup_all=False, ignore_suicide=False,
            subgraphs_on=False):

        # If graph extent is not given, use visualization settings.
        if start_point_string is None:
            start_point_string = self.cfg['visualization']['initial cycle point']

        if stop_point_string is None:
            vfcp = self.cfg['visualization']['final cycle point']
            if vfcp:
                try:
                    stop_point_string = str(get_point_relative(
                        vfcp,
                        get_point(start_point_string)).standardise())
                except ValueError:
                    stop_point_string = str(get_point(
                        vfcp).standardise())

        if stop_point_string is not None:
            if get_point(stop_point_string) < get_point(start_point_string):
                # Avoid a null graph.
                stop_point_string = start_point_string

        gr_edges = self.get_graph_raw(
            start_point_string, stop_point_string,
            group_nodes, ungroup_nodes, ungroup_recursive,
            group_all, ungroup_all
        )
        graph = graphing.CGraph(
                self.suite, self.suite_polling_tasks, self.cfg['visualization'])
        graph.add_edges( gr_edges, ignore_suicide )
        if subgraphs_on:
            graph.add_cycle_point_subgraphs( gr_edges )
        return graph

    def get_node_labels( self, start_point_string, stop_point_string):
        graph = self.get_graph( start_point_string, stop_point_string,
                                ungroup_all=True )
        return [ i.attr['label'].replace('\\n','.') for i in graph.nodes() ]

    def close_families( self, nlid, nrid ):
        # Generate final node names, replacing family members with
        # family nodes if requested.

        members = self.runtime['first-parent descendants']

        lname, lpoint_string = None, None
        rname, rpoint_string = None, None
        nr, nl = None, None
        if nlid:
            one, two = TaskID.split(nlid)
            lname = one
            lpoint_string = two
            nl = nlid
        if nrid:
            one, two = TaskID.split(nrid)
            rname = one
            rpoint_string = two
            nr = nrid

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
                nl = TaskID.get(fam, lpoint_string)
                nr = TaskID.get(fam, rpoint_string)
                break
            elif lname in members[fam]:
                # l is a member of fam
                nl = TaskID.get(fam, lpoint_string)
            elif rname in members[fam]:
                # r is a member of fam
                nr = TaskID.get(fam, rpoint_string)

        return nl, nr

    def load_graph(self):
        if flags.verbose:
            print "Parsing the dependency graph"

        start_up_tasks = self.cfg['scheduling']['special tasks']['start-up']
        if start_up_tasks:
            set_syntax_version(
                VERSION_PREV,
                "start-up tasks: %s" % ",".join(start_up_tasks)
            )
        back_comp_initial_tasks = list(start_up_tasks)

        has_non_async_graphs = False

        section_seq_map = {}

        # Set up our backwards-compatibility handling of async graphs.
        async_graph = self.cfg['scheduling']['dependencies']['graph']
        if async_graph:
            section = get_sequence_cls().get_async_expr()
            async_dependencies = self.parse_graph(
                section, async_graph, section_seq_map=section_seq_map,
                return_all_dependencies=True
            )
            for left, left_output, right in async_dependencies:
                if left:
                    back_comp_initial_tasks.append(left)
                if right:
                    back_comp_initial_tasks.append(right)

        # Create a stack of sections (sequence strings) and graphs.
        items = []
        for item, value in self.cfg['scheduling']['dependencies'].items():
            if item == 'graph':
                continue
            has_non_async_graphs = True
            items.append((item, value, back_comp_initial_tasks))

        back_comp_initial_dep_points = {}
        initial_point = get_point(
            self.cfg['scheduling']['initial cycle point'])
        back_comp_initial_tasks_graphed = []
        while items:
            item, value, tasks_to_prune = items.pop(0)

            # If the section consists of more than one sequence, split it up.
            if re.search("(?![^(]+\)),", item):
                new_items = re.split("(?![^(]+\)),", item)
                for new_item in new_items:
                    items.append((new_item.strip(), value, tasks_to_prune))
                continue

            try:
                graph = value['graph']
            except KeyError:
                continue
            if not graph:
                continue

            section = item
            special_dependencies = self.parse_graph(
                section, graph, section_seq_map=section_seq_map,
                tasks_to_prune=tasks_to_prune
            )
            if special_dependencies and tasks_to_prune:
                section_seq = get_sequence(
                    section,
                    self.cfg['scheduling']['initial cycle point'],
                    self.cfg['scheduling']['final cycle point']
                )
                first_point = section_seq.get_first_point(initial_point)
                for dep in special_dependencies:
                    # Set e.g. (foo, fail, bar) => foo, foo[^]:fail => bar.
                    left, left_output, right = dep
                    if left in back_comp_initial_tasks:
                        # Start-up/Async tasks now always run at R1.
                        pure_left_dep = (left, None, None)
                        back_comp_initial_dep_points.setdefault(
                            pure_left_dep, [])
                        back_comp_initial_dep_points[pure_left_dep].append(
                            first_point)
                    # Sort out the dependencies on R1 at R1/some-time.
                    back_comp_initial_dep_points.setdefault(tuple(dep), [])
                    back_comp_initial_dep_points[tuple(dep)].append(
                        first_point)

        back_comp_initial_section_graphs = {}
        for dep in sorted(back_comp_initial_dep_points):
            first_common_point = min(back_comp_initial_dep_points[dep])
            at_initial_point = (first_common_point == initial_point)
            left, left_output, right = dep
            graph_text = left
            if not at_initial_point:
                # Reference the initial left task.
                left_points = (
                    back_comp_initial_dep_points[(left, None, None)])
                left_min_point = min(left_points)
                if left_min_point == initial_point:
                    graph_text += "[^]"
                elif left_min_point != first_common_point:
                    graph_text += "[%s]" % left_min_point
            if left_output:
                if left_output == "finish":
                    graph_text = (graph_text + ":succeed" + " | " +
                                  graph_text + ":fail")
                else:
                    graph_text += ":" + left_output
            if right:
                graph_text += " => " + right
            if at_initial_point:
                section = get_sequence_cls().get_async_expr()
            else:
                section = get_sequence_cls().get_async_expr(
                    first_common_point)
            back_comp_initial_section_graphs.setdefault(section, [])
            back_comp_initial_section_graphs[section].append(graph_text)

        for section in sorted(back_comp_initial_section_graphs):
            total_graph_text = "\n".join(
                back_comp_initial_section_graphs[section])
            if self.validation:
                print ("# REPLACING START-UP/ASYNC DEPENDENCIES " +
                       "WITH AN R1* SECTION")
                print "# (VARYING INITIAL CYCLE POINT MAY AFFECT VALIDITY)"
                print "        [[[" + section + "]]]"
                print "            " + 'graph = """'
                print total_graph_text + '\n"""'
            self.parse_graph(
                section, total_graph_text,
                section_seq_map=section_seq_map, tasks_to_prune=[]
            )

    def parse_graph(self, section, graph, section_seq_map=None,
                    tasks_to_prune=None, return_all_dependencies=False):
        """Parse a multi-line graph string for section.

        section should be a string like "R1" or "T00".
        graph should be a single or multi-line string like "foo => bar"
        section_seq_map should be a dictionary that indexes cycling
        sequences by their section string
        tasks_to_prune is a list of task names that should be
        automatically removed when processing graph
        return_all_dependencies is a boolean that, if True, returns a
        list of task dependencies - e.g. [('foo', 'start', 'bar')] for
        a graph of 'foo:start => bar'.

        """

        sec = section

        if section in section_seq_map:
            seq = section_seq_map[section]
        else:
            seq = get_sequence(
                section,
                self.cfg['scheduling']['initial cycle point'],
                self.cfg['scheduling']['final cycle point']
            )
            section_seq_map[section] = seq
        offset_seq_map = {}

        if seq not in self.sequences:
            self.sequences.append(seq)

        # split the graph string into successive lines
        special_dependencies = []
        for xline in graph.splitlines():
            # strip comments
            line = re.sub('#.*', '', xline).strip()
            # ignore blank lines
            if not line:
                continue
            # generate pygraphviz graph nodes and edges, and task definitions
            special_dependencies.extend(self.process_graph_line(
                line, section, seq, offset_seq_map,
                tasks_to_prune=tasks_to_prune,
                return_all_dependencies=return_all_dependencies
            ))
        return special_dependencies

    def get_taskdef(self, name):
        """Get the dense task runtime."""
        # (TaskDefError caught above)
        try:
            rtcfg = self.cfg['runtime'][name]
        except KeyError:
            raise TaskNotDefinedError(name)
        # We may want to put in some handling for cases of changing the
        # initial cycle via restart (accidentally or otherwise).

        # Get the taskdef object for generating the task proxy class
        taskd = TaskDef(name, rtcfg, self.run_mode, self.start_point)

        # TODO - put all taskd.foo items in a single config dict
        # Set cold-start task indicators.
        if name in self.cfg['scheduling']['special tasks']['cold-start']:
            taskd.is_coldstart = True

        # Set clock-triggered tasks.
        if name in self.clock_offsets:
            taskd.clocktrigger_offset = self.clock_offsets[name]

        taskd.sequential = (
            name in self.cfg['scheduling']['special tasks']['sequential'])

        foo = copy(self.runtime['linearized ancestors'][name])
        foo.reverse()
        taskd.namespace_hierarchy = foo

        return taskd

    def get_task_proxy(self, name, *args, **kwargs):
        """Return a task proxy for a named task."""
        try:
            tdef = self.taskdefs[name]
        except KeyError:
            raise TaskNotDefinedError(name)
        return TaskProxy(tdef, *args, **kwargs)

    def describe(self, name):
        """Return title and description of the named task."""
        return self.taskdefs[name].describe()
