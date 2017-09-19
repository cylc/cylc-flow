#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"""Parse and validate the suite definition file

Do some consistency checking, then construct task proxy objects and graph
structures.
"""


from copy import copy
from fnmatch import fnmatchcase
import os
import re
import traceback

from cylc.c3mro import C3
from cylc.conditional_simplifier import ConditionalSimplifier
from cylc.exceptions import CylcError
from cylc.graph_parser import GraphParser
from cylc.param_expand import NameExpander
from cylc.cfgspec.suite import RawSuiteConfig
from cylc.cycling.loader import (
    get_point, get_point_relative, get_interval, get_interval_cls,
    get_sequence, get_sequence_cls, init_cyclers, INTEGER_CYCLING_TYPE,
    ISO8601_CYCLING_TYPE)
from cylc.cycling import IntervalParsingError
from cylc.envvar import check_varnames
import cylc.flags
from cylc.graphnode import GraphNodeParser, GraphNodeError
from cylc.print_tree import print_tree
from cylc.taskdef import TaskDef, TaskDefError
from cylc.task_id import TaskID
from cylc.task_trigger import TaskTrigger, Dependency
from cylc.wallclock import get_current_time_string
from isodatetime.data import Calendar
from isodatetime.parsers import DurationParser
from parsec.OrderedDict import OrderedDictWithDefaults
from parsec.util import replicate
from cylc.suite_logging import OUT, ERR
from cylc.task_outputs import TASK_OUTPUT_SUCCEEDED

RE_CLOCK_OFFSET = re.compile(r'(' + TaskID.NAME_RE + r')(?:\(\s*(.+)\s*\))?')
RE_EXT_TRIGGER = re.compile(r'(.*)\s*\(\s*(.+)\s*\)\s*')
RE_SEC_MULTI_SEQ = re.compile(r'(?![^(]+\)),')
RE_SUITE_NAME_VAR = re.compile(r'\${?CYLC_SUITE_(REG_)?NAME}?')
RE_TASK_NAME_VAR = re.compile(r'\${?CYLC_TASK_NAME}?')
NUM_RUNAHEAD_SEQ_POINTS = 5  # Number of cycle points to look at per sequence.

# Message trigger offset regex.
BCOMPAT_MSG_RE_C6 = re.compile(r'^(.*)\[\s*(([+-])?\s*(.*))?\s*\](.*)$')


class SuiteConfigError(Exception):
    """
    Attributes:
        message - what the problem is.
        TODO - element - config element causing the problem
    """
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)

# TODO: separate config for run and non-run purposes?


class SuiteConfig(object):
    """Class for suite configuration items and derived quantities."""

    Q_DEFAULT = 'default'
    TASK_EVENT_TMPL_KEYS = (
        'event', 'suite', 'point', 'name', 'submit_num', 'id', 'message')

    def __init__(self, suite, fpath, template_vars=None,
                 owner=None, run_mode='live', is_validate=False, strict=False,
                 collapsed=[], cli_initial_point_string=None,
                 cli_start_point_string=None, cli_final_point_string=None,
                 is_reload=False, output_fname=None,
                 vis_start_string=None, vis_stop_string=None,
                 mem_log_func=None):

        self.mem_log = mem_log_func
        if mem_log_func is None:
            self.mem_log = lambda *a: False
        self.mem_log("config.py:config.py: start init config")
        self.suite = suite  # suite name
        self.fpath = fpath  # suite definition
        self.fdir = os.path.dirname(fpath)
        self.owner = owner
        self.run_mode = run_mode
        self.strict = strict
        self.naked_dummy_tasks = []
        self.edges = {}
        self.taskdefs = {}
        self.initial_point = None
        self.start_point = None
        self.first_graph = True
        self.clock_offsets = {}
        self.expiration_offsets = {}
        self.ext_triggers = {}
        self.suite_polling_tasks = {}
        self.vis_start_point_string = vis_start_string
        self.vis_stop_point_string = vis_stop_string
        self._last_graph_raw_id = None
        self._last_graph_raw_edges = []

        self.sequences = []
        self.actual_first_point = None
        self._start_point_for_actual_first_point = None

        self.task_param_vars = {}
        self.custom_runahead_limit = None
        self.max_num_active_cycle_points = None

        # runtime hierarchy dicts keyed by namespace name:
        self.runtime = {
            # lists of parent namespaces
            'parents': {},
            # lists of C3-linearized ancestor namespaces
            'linearized ancestors': {},
            # lists of first-parent ancestor namepaces
            'first-parent ancestors': {},
            # lists of all descendant namespaces
            # (not including the final tasks)
            'descendants': {},
            # lists of all descendant namespaces from the first-parent
            # hierarchy (first parents are collapsible in suite
            # visualization)
            'first-parent descendants': {},
        }
        # tasks
        self.leaves = []
        # one up from root
        self.feet = []

        # parse, upgrade, validate the suite, but don't expand with default
        # items
        self.mem_log("config.py: before RawSuiteConfig init")
        self.pcfg = RawSuiteConfig(fpath, output_fname, template_vars)
        self.mem_log("config.py: after RawSuiteConfig init")
        self.mem_log("config.py: before get(sparse=True")
        self.cfg = self.pcfg.get(sparse=True)
        self.mem_log("config.py: after get(sparse=True)")

        # First check for the essential scheduling section.
        if 'scheduling' not in self.cfg:
            raise SuiteConfigError("ERROR: missing [scheduling] section.")
        if 'dependencies' not in self.cfg['scheduling']:
            raise SuiteConfigError(
                "ERROR: missing [scheduling][[dependencies]] section.")
        # (The check that 'graph' is definied is below).
        # The two runahead limiting schemes are mutually exclusive.
        rlim = self.cfg['scheduling'].get('runahead limit', None)
        mact = self.cfg['scheduling'].get('max active cycle points', None)
        if rlim is not None and mact is not None:
            raise SuiteConfigError(
                "ERROR: use 'runahead limit' OR "
                "'max active cycle points', not both")

        # Override the suite defn with an initial point from the CLI.
        if cli_initial_point_string is not None:
            self.cfg['scheduling']['initial cycle point'] = (
                cli_initial_point_string)

        dependency_map = self.cfg.get('scheduling', {}).get(
            'dependencies', {})

        if not self.is_graph_defined(dependency_map):
            raise SuiteConfigError('No suite dependency graph defined.')

        if 'cycling mode' not in self.cfg.get('scheduling', {}):
            # Auto-detect integer cycling for pure async graph suites.
            if dependency_map.get('graph'):
                # There is an async graph setting.
                # If it is by itself, it is integer shorthand.
                # If there are cycling graphs as well, it is obsolete
                # (pre cylc-6) syntax.
                just_has_async_graph = True
                non_async_item = None
                for item, value in dependency_map.items():
                    if item != 'graph' and value.get('graph'):
                        just_has_async_graph = False
                        non_async_item = item
                        break
                icp = self.cfg['scheduling'].get('initial cycle point')
                fcp = self.cfg['scheduling'].get('final cycle point')
                if just_has_async_graph and not (
                        icp in [None, "1"] and fcp in [None, icp]):
                    raise SuiteConfigError(
                        'Conflicting syntax: integer vs ' +
                        'cycling suite: ' +
                        'are you missing a [dependencies][[[R1]]] section?')
                if just_has_async_graph:
                    # There aren't any other graphs, so set integer cycling.
                    self.cfg['scheduling']['cycling mode'] = (
                        INTEGER_CYCLING_TYPE
                    )
                    if 'initial cycle point' not in self.cfg['scheduling']:
                        self.cfg['scheduling']['initial cycle point'] = "1"
                    if 'final cycle point' not in self.cfg['scheduling']:
                        self.cfg['scheduling']['final cycle point'] = "1"
                else:
                    # Looks like cylc-5 mixed-async.
                    raise SuiteConfigError(
                        'Obsolete syntax: mixed integer [dependencies]graph ' +
                        'with cycling [dependencies][{0}]'.format(
                            non_async_item)
                    )

        # allow test suites with no [runtime]:
        if 'runtime' not in self.cfg:
            self.cfg['runtime'] = OrderedDictWithDefaults()

        if 'root' not in self.cfg['runtime']:
            self.cfg['runtime']['root'] = OrderedDictWithDefaults()

        try:
            parameter_values = self.cfg['cylc']['parameters']
        except KeyError:
            # (Suite config defaults not put in yet.)
            parameter_values = {}
        try:
            parameter_templates = self.cfg['cylc']['parameter templates']
        except KeyError:
            parameter_templates = {}
        # parameter values and templates are normally needed together.
        self.parameters = (parameter_values, parameter_templates)

        if cylc.flags.verbose:
            OUT.info(
                "Expanding [runtime] namespace lists and parameters")

        # Set default parameter expansion templates if necessary.
        for pname, pvalues in parameter_values.items():
            if pvalues and pname not in parameter_templates:
                if all(isinstance(pvalue, int) for pvalue in pvalues):
                    parameter_templates[pname] = r'_%s%%(%s)0%dd' % (
                        pname, pname, len(str(max(pvalues))))
                else:
                    # Don't prefix string values with the parameter name.
                    parameter_templates[pname] = r'_%%(%s)s' % pname

        # Expand parameters in 'special task' lists.
        if 'special tasks' in self.cfg['scheduling']:
            for spec, names in self.cfg['scheduling']['special tasks'].items():
                self.cfg['scheduling']['special tasks'][spec] = (
                    self._expand_name_list(names))

        # Expand parameters in internal queue member lists.
        if 'queues' in self.cfg['scheduling']:
            for queue, cfg in self.cfg['scheduling']['queues'].items():
                if 'members' not in cfg:
                    continue
                self.cfg['scheduling']['queues'][queue]['members'] = (
                    self._expand_name_list(cfg['members']))

        self.mem_log("config.py: before _expand_runtime")
        self._expand_runtime()
        self.mem_log("config.py: after _expand_runtime")

        self.ns_defn_order = self.cfg['runtime'].keys()

        # check var names before inheritance to avoid repetition
        self.check_env_names()

        self.mem_log("config.py: before compute_family_tree")
        # do sparse inheritance
        self.compute_family_tree()
        self.mem_log("config.py: after compute_family_tree")
        self.mem_log("config.py: before inheritance")
        self.compute_inheritance()
        self.mem_log("config.py: after inheritance")

        # self.print_inheritance() # (debugging)

        # filter task environment variables after inheritance
        self.filter_env()

        # Now add config defaults.  Items added prior to this ends up in the
        # sparse dict (e.g. parameter-expanded namepaces).
        self.mem_log("config.py: before get(sparse=False)")
        self.cfg = self.pcfg.get(sparse=False)
        self.mem_log("config.py: after get(sparse=False)")

        # after the call to init_cyclers, we can start getting proper points.
        init_cyclers(self.cfg)

        # Running in UTC time? (else just use the system clock)
        cylc.flags.utc = self.cfg['cylc']['UTC mode']
        # Capture cycling mode
        cylc.flags.cycling_mode = self.cfg['scheduling']['cycling mode']

        # Initial point from suite definition (or CLI override above).
        icp = self.cfg['scheduling']['initial cycle point']
        if icp is None:
            raise SuiteConfigError(
                "This suite requires an initial cycle point.")
        if icp == "now":
            icp = get_current_time_string()
        self.initial_point = get_point(icp).standardise()
        self.cfg['scheduling']['initial cycle point'] = str(self.initial_point)
        if cli_start_point_string:
            # Warm start from a point later than initial point.
            if cli_start_point_string == "now":
                cli_start_point_string = get_current_time_string()
            cli_start_point = get_point(cli_start_point_string).standardise()
            self.start_point = cli_start_point
        else:
            # Cold start.
            self.start_point = self.initial_point

        # Validate initial cycle point against any constraints
        if self.cfg['scheduling']['initial cycle point constraints']:
            valid_icp = False
            for entry in (
                    self.cfg['scheduling']['initial cycle point constraints']):
                possible_pt = get_point_relative(
                    entry, self.initial_point
                ).standardise()
                if self.initial_point == possible_pt:
                    valid_icp = True
                    break
            if not valid_icp:
                constraints_str = str(
                    self.cfg['scheduling']['initial cycle point constraints'])
                raise SuiteConfigError(
                    ("Initial cycle point %s does not meet the constraints " +
                     "%s") % (
                        str(self.initial_point),
                        constraints_str
                    )
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
                        self.initial_point
                    ).standardise()
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
            raise SuiteConfigError(
                "The initial cycle point:" +
                str(self.initial_point) + " is after the final cycle point:" +
                str(final_point) + ".")

        # Validate final cycle point against any constraints
        if (final_point is not None and
                self.cfg['scheduling']['final cycle point constraints']):
            valid_fcp = False
            for entry in (
                    self.cfg['scheduling']['final cycle point constraints']):
                possible_pt = get_point_relative(
                    entry, final_point).standardise()
                if final_point == possible_pt:
                    valid_fcp = True
                    break
            if not valid_fcp:
                constraints_str = str(
                    self.cfg['scheduling']['final cycle point constraints'])
                raise SuiteConfigError(
                    "Final cycle point %s does not meet the constraints %s" % (
                        str(final_point), constraints_str))

        # Parse special task cycle point offsets, and replace family names.
        if cylc.flags.verbose:
            OUT.info("Parsing [special tasks]")
        for s_type in self.cfg['scheduling']['special tasks']:
            result = copy(self.cfg['scheduling']['special tasks'][s_type])
            extn = ''
            for item in self.cfg['scheduling']['special tasks'][s_type]:
                name = item
                if s_type == 'external-trigger':
                    match = RE_EXT_TRIGGER.match(item)
                    if match is None:
                        raise SuiteConfigError(
                            "ERROR: Illegal %s spec: %s" % (s_type, item)
                        )
                    name, ext_trigger_msg = match.groups()
                    extn = "(" + ext_trigger_msg + ")"

                elif s_type in ['clock-trigger', 'clock-expire']:
                    match = RE_CLOCK_OFFSET.match(item)
                    if match is None:
                        raise SuiteConfigError(
                            "ERROR: Illegal %s spec: %s" % (s_type, item)
                        )
                    if (self.cfg['scheduling']['cycling mode'] !=
                            Calendar.MODE_GREGORIAN):
                        raise SuiteConfigError(
                            "ERROR: %s tasks require "
                            "[scheduling]cycling mode=%s" % (
                                s_type, Calendar.MODE_GREGORIAN)
                        )
                    name, offset_string = match.groups()
                    if not offset_string:
                        offset_string = "PT0M"
                    if cylc.flags.verbose:
                        if offset_string.startswith("-"):
                            ERR.warning(
                                "%s offsets are normally positive: %s" % (
                                    s_type, item))
                    try:
                        offset_interval = (
                            get_interval(offset_string).standardise())
                    except IntervalParsingError:
                        raise SuiteConfigError(
                            "ERROR: Illegal %s spec: %s" % (
                                s_type, offset_string))
                    extn = "(" + offset_string + ")"

                # Replace family names with members.
                if name in self.runtime['descendants']:
                    result.remove(item)
                    for member in self.runtime['descendants'][name]:
                        if member in self.runtime['descendants']:
                            # (sub-family)
                            continue
                        result.append(member + extn)
                        if s_type == 'clock-trigger':
                            self.clock_offsets[member] = offset_interval
                        if s_type == 'clock-expire':
                            self.expiration_offsets[member] = offset_interval
                        if s_type == 'external-trigger':
                            self.ext_triggers[member] = ext_trigger_msg
                elif s_type == 'clock-trigger':
                    self.clock_offsets[name] = offset_interval
                elif s_type == 'clock-expire':
                    self.expiration_offsets[name] = offset_interval
                elif s_type == 'external-trigger':
                    self.ext_triggers[name] = self.dequote(ext_trigger_msg)

            self.cfg['scheduling']['special tasks'][s_type] = result

        self.collapsed_families_rc = (
            self.cfg['visualization']['collapsed families'])
        for fam in self.collapsed_families_rc:
            if fam not in self.runtime['first-parent descendants']:
                raise SuiteConfigError(
                    'ERROR [visualization]collapsed families: '
                    '%s is not a first parent' % fam)

        if is_reload:
            # on suite reload retain an existing state of collapse
            # (used by the "cylc graph" viewer)
            self.closed_families = collapsed
        else:
            self.closed_families = self.collapsed_families_rc
        for cfam in self.closed_families:
            if cfam not in self.runtime['descendants']:
                self.closed_families.remove(cfam)
                if not is_reload and cylc.flags.verbose:
                    ERR.warning(
                        '[visualization][collapsed families]: ' +
                        'family ' + cfam + ' not defined')

        # check for run mode override at suite level
        if self.cfg['cylc']['force run mode']:
            self.run_mode = self.cfg['cylc']['force run mode']

        self.process_directories()

        self.mem_log("config.py: before load_graph()")
        self.load_graph()
        if not is_validate:
            GraphNodeParser.get_inst().clear()
        self.mem_log("config.py: after load_graph()")

        self.compute_runahead_limits()

        self.configure_queues()

        if self.run_mode in ['simulation', 'dummy', 'dummy-local']:
            self.configure_sim_modes()

        self.configure_suite_state_polling_tasks()

        # Warn or abort (if --strict) if naked dummy tasks (no runtime
        # section) are found in graph or queue config.
        if len(self.naked_dummy_tasks) > 0:
            if self.strict or cylc.flags.verbose:
                err_msg = ('naked dummy tasks detected (no entry'
                           ' under [runtime]):')
                for ndt in self.naked_dummy_tasks:
                    err_msg += '\n+\t' + str(ndt)
                ERR.warning(err_msg)
            if self.strict:
                raise SuiteConfigError(
                    'ERROR: strict validation fails naked dummy tasks')

        if is_validate:
            self.check_tasks()

        # Check that external trigger messages are only used once (they have to
        # be discarded immediately to avoid triggering the next instance of the
        # just-triggered task).
        seen = {}
        for name, tdef in self.taskdefs.items():
            for msg in tdef.external_triggers:
                if msg not in seen:
                    seen[msg] = name
                else:
                    ERR.error(
                        "External trigger '%s'\n  used in tasks %s and %s." % (
                            msg, name, seen[msg]))
                    raise SuiteConfigError(
                        "ERROR: external triggers must be used only once.")

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

        if cylc.flags.verbose:
            OUT.info("Checking [visualization] node attributes")
            # TODO - these should probably be done in non-verbose mode too.
            # 1. node groups should contain valid namespace names
            nspaces = self.cfg['runtime'].keys()
            bad = {}
            for ng, mems in ngs.items():
                n_bad = []
                for mem in mems:
                    if mem not in nspaces:
                        n_bad.append(mem)
                if n_bad:
                    bad[ng] = n_bad
            if bad:
                err_msg = "undefined node group members"
                for ng, mems in bad.items():
                    err_msg += "\n+ " + ng + ":\t,".join(mems)
                ERR.warning(err_msg)

            # 2. node attributes must refer to node groups or namespaces
            bad = []
            for na in self.cfg['visualization']['node attributes']:
                if na not in ngs and na not in nspaces:
                    bad.append(na)
            if bad:
                err_msg = "undefined node attribute targets"
                for na in bad:
                    err_msg += "\n+ " + str(na)
                ERR.warning(err_msg)

        # 3. node attributes must be lists of quoted "key=value" pairs.
        fail = False
        for node, attrs in (
                self.cfg['visualization']['node attributes'].items()):
            for attr in attrs:
                # Check form is 'name = attr'.
                if attr.count('=') != 1:
                    fail = True
                    ERR.error(
                        "[visualization][node attributes]%s = %s" % (
                            node, attr))
        if fail:
            raise SuiteConfigError("Node attributes must be of the form "
                                   "'key1=value1', 'key2=value2', etc.")

        # (Note that we're retaining 'default node attributes' even
        # though this could now be achieved by styling the root family,
        # because putting default attributes for root in the suite.rc spec
        # results in root appearing last in the ordered dict of node
        # names, so it overrides the styling for lesser groups and
        # nodes, whereas the reverse is needed - fixing this would
        # require reordering task_attr in lib/cylc/graphing.py).

        self.leaves = self.get_task_name_list()
        for ancestors in self.runtime['first-parent ancestors'].values():
            try:
                foot = ancestors[-2]  # one back from 'root'
            except IndexError:
                pass
            else:
                if foot not in self.feet:
                    self.feet.append(foot)

        # CLI override for visualization settings.
        if self.vis_start_point_string:
            self.cfg['visualization']['initial cycle point'] = (
                self.vis_start_point_string)
        if self.vis_stop_point_string:
            self.cfg['visualization']['final cycle point'] = (
                self.vis_stop_point_string)

        # For static visualization, start point defaults to suite initial
        # point; stop point must be explicit with initial point, or None.
        if self.cfg['visualization']['initial cycle point'] is None:
            self.cfg['visualization']['initial cycle point'] = (
                self.cfg['scheduling']['initial cycle point'])
            # If viz initial point is None don't accept a final point.
            if self.cfg['visualization']['final cycle point'] is not None:
                if cylc.flags.verbose:
                    ERR.warning(
                        "ignoring [visualization]final cycle point\n"
                        "(it must be defined with an initial cycle point)")
                self.cfg['visualization']['final cycle point'] = None

        vfcp = self.cfg['visualization']['final cycle point']
        if vfcp:
            try:
                vfcp = get_point_relative(
                    self.cfg['visualization']['final cycle point'],
                    self.initial_point).standardise()
            except ValueError:
                vfcp = get_point(
                    self.cfg['visualization']['final cycle point']
                ).standardise()
        else:
            vfcp = None

        # A viz final point can't be beyond the suite final point.
        if vfcp is not None and final_point is not None:
            if vfcp > final_point:
                self.cfg['visualization']['final cycle point'] = str(
                    final_point)
        # Replace suite name in suite  URL.
        url = self.cfg['meta']['URL']
        if url is not '':
            self.cfg['meta']['URL'] = RE_SUITE_NAME_VAR.sub(self.suite, url)

        # Replace suite and task name in task URLs.
        for name, cfg in self.cfg['runtime'].items():
            if cfg['meta']['URL']:
                cfg['meta']['URL'] = RE_TASK_NAME_VAR.sub(
                    name, cfg['meta']['URL'])
                cfg['meta']['URL'] = RE_SUITE_NAME_VAR.sub(
                    self.suite, cfg['meta']['URL'])

        if is_validate:
            self.mem_log("config.py: before _check_circular()")
            self._check_circular()
            self.mem_log("config.py: after _check_circular()")

        self.mem_log("config.py: end init config")

    def _check_circular(self):
        """Check for circular dependence in graph."""
        start_point_string = (
            self.cfg['visualization']['initial cycle point'])
        lhs2rhss = {}  # left hand side to right hand sides
        rhs2lhss = {}  # right hand side to left hand sides
        for lhs, rhs in self.get_graph_raw(
                start_point_string, stop_point_string=None, is_validate=True):
            lhs2rhss.setdefault(lhs, set())
            lhs2rhss[lhs].add(rhs)
            rhs2lhss.setdefault(rhs, set())
            rhs2lhss[rhs].add(lhs)
        self._check_circular_helper(lhs2rhss, rhs2lhss)
        if rhs2lhss:
            # Before reporting circular dependence, pick out all the edges with
            # no outgoings.
            self._check_circular_helper(rhs2lhss, lhs2rhss)
            err_msg = ''
            for rhs, lhss in sorted(rhs2lhss.items()):
                for lhs in sorted(lhss):
                    err_msg += '  %s => %s' % (
                        TaskID.get(*lhs), TaskID.get(*rhs))
            if err_msg:
                raise SuiteConfigError(
                    'ERROR: circular edges detected:' + err_msg)

    @staticmethod
    def _check_circular_helper(x2ys, y2xs):
        """Topological elimination.

        An implementation of Kahn's algorithm for topological sorting, but
        only use the part for pulling out starter nodes with no incoming
        edges. See https://en.wikipedia.org/wiki/Topological_sorting

        x2ys is a map of {x1: [y1, y2, ...], ...}
        to map edges using x's as keys, such as x1 => y1, x1 => y2, etc

        y2xs is a map of {y3: [x4, x5, ...], ...}
        to map edges using y's as keys, such as x4 => y3, x5 => y3, etc
        """
        # Starter x nodes are those with no incoming, i.e.
        # x nodes that never appear as a y.
        sxs = set(x01 for x01 in x2ys if x01 not in y2xs)
        while sxs:
            sx01 = sxs.pop()
            for y01 in x2ys[sx01]:
                y2xs[y01].remove(sx01)
                if not y2xs[y01]:
                    if y01 in x2ys:
                        # No need to look at this again if it does not have any
                        # outgoing.
                        sxs.add(y01)
                    del y2xs[y01]
            del x2ys[sx01]

    def _expand_name_list(self, orig_names):
        """Expand any parameters in lists of names."""
        name_expander = NameExpander(self.parameters)
        exp_names = []
        for orig_name in orig_names:
            exp_names += [name for name, _ in name_expander.expand(orig_name)]
        return exp_names

    def _expand_runtime(self):
        """Expand [runtime] name lists or parameterized names.

        This makes individual runtime namespaces out of any headings that
        represent multiple namespaces, like [[foo, bar]] or [[foo<m,n>]].
        It requires replicating the sparse runtime OrderedDict into a new
        OrderedDict - we can't just stick expanded names on the end because the
        order matters (for add-or-override by repeated namespaces).

        TODO - this will have an impact on memory footprint for large suites
        with a lot of runtime config. We should consider ditching OrderedDict
        and instead using an ordinary dict with a separate list of keys.
        """
        if (not self.parameters[0] and
                not any(',' in ns for ns in self.cfg['runtime'])):
            # No parameters, no namespace lists: no expansion needed.
            return

        newruntime = OrderedDictWithDefaults()
        name_expander = NameExpander(self.parameters)
        for namespace_heading, namespace_dict in self.cfg['runtime'].items():
            for name, indices in name_expander.expand(namespace_heading):
                if name not in newruntime:
                    newruntime[name] = OrderedDictWithDefaults()
                # Put parameter index values in task environment.
                replicate(newruntime[name], namespace_dict)
                if indices:
                    new_environ = OrderedDictWithDefaults()
                    self.task_param_vars[name] = {}
                    for p_name, p_val in indices.items():
                        p_var_name = 'CYLC_TASK_PARAM_%s' % p_name
                        self.task_param_vars[name][p_var_name] = p_val
                    if 'environment' in newruntime[name]:
                        for k, v in newruntime[name]['environment'].items():
                            new_environ[k] = v
                    newruntime[name]['environment'] = new_environ
                    if 'inherit' in newruntime[name]:
                        parents = newruntime[name]['inherit']
                        origin = 'inherit = %s' % ' '.join(parents)
                        repl_parents = []
                        for parent in parents:
                            repl_parents.append(name_expander.replace_params(
                                parent, indices, origin))
                        newruntime[name]['inherit'] = repl_parents
        self.cfg['runtime'] = newruntime

        # Parameter expansion of visualization node attributes. TODO - do vis
        # 'node groups' too, or deprecate them (use families in 'node attrs').
        name_expander = NameExpander(self.parameters)
        expanded_node_attrs = OrderedDictWithDefaults()
        if 'visualization' not in self.cfg:
            self.cfg['visualization'] = OrderedDictWithDefaults()
        if 'node attributes' not in self.cfg['visualization']:
            self.cfg['visualization']['node attributes'] = (
                OrderedDictWithDefaults())
        for node, val in self.cfg['visualization']['node attributes'].items():
            for name, _ in name_expander.expand(node):
                expanded_node_attrs[name] = val
        self.cfg['visualization']['node attributes'] = expanded_node_attrs

    @staticmethod
    def is_graph_defined(dependency_map):
        for item, value in dependency_map.items():
            if item == 'graph':
                # Async graph.
                if value != '':
                    return True
            else:
                # Cycling section.
                for subitem, subvalue in value.items():
                    if subitem == 'graph':
                        if subvalue != '':
                            return True
        return False

    @staticmethod
    def dequote(s):
        """Strip quotes off a string."""
        if (s[0] == s[-1]) and s.startswith(("'", '"')):
            return s[1:-1]
        return s

    def check_env_names(self):
        # check for illegal environment variable names
        bad = {}
        for label in self.cfg['runtime']:
            res = []
            if 'environment' in self.cfg['runtime'][label]:
                res = check_varnames(self.cfg['runtime'][label]['environment'])
            if res:
                bad[label] = res
        if bad:
            err_msg = "bad env variable names:"
            for label, vars_ in bad.items():
                err_msg += '\nNamespace:\t' + label
                for var in vars_:
                    err_msg += "\n\t\t" + var
            ERR.error(err_msg)
            raise SuiteConfigError(
                "Illegal environment variable name(s) detected")

    def filter_env(self):
        # filter environment variables after sparse inheritance
        for ns in self.cfg['runtime'].values():
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

            nenv = OrderedDictWithDefaults()
            for key, val in oenv.items():
                if (not fincl or key in fincl) and key not in fexcl:
                    nenv[key] = val
            ns['environment'] = nenv

    def compute_family_tree(self):
        first_parents = {}
        demoted = {}
        for name in self.cfg['runtime']:
            if name == 'root':
                self.runtime['parents'][name] = []
                first_parents[name] = []
                continue
            # get declared parents, with implicit inheritance from root.
            pts = self.cfg['runtime'][name].get('inherit', ['root'])
            if not pts:
                pts = ['root']
            for p in pts:
                if p == "None":
                    # see just below
                    continue
                if p not in self.cfg['runtime']:
                    raise SuiteConfigError(
                        "ERROR, undefined parent for " + name + ": " + p)
            if pts[0] == "None":
                if len(pts) < 2:
                    raise SuiteConfigError(
                        "ERROR: null parentage for " + name)
                demoted[name] = pts[1]
                pts = pts[1:]
                first_parents[name] = ['root']
            else:
                first_parents[name] = [pts[0]]
            self.runtime['parents'][name] = pts

        if cylc.flags.verbose and demoted:
            log_msg = "First parent(s) demoted to secondary:\n"
            for n, p in demoted.items():
                log_msg += " + %s as parent of '%s'\n" % (p, n)
            OUT.info(log_msg)

        c3 = C3(self.runtime['parents'])
        c3_single = C3(first_parents)

        for name in self.cfg['runtime']:
            try:
                self.runtime['linearized ancestors'][name] = c3.mro(name)
                self.runtime['first-parent ancestors'][name] = (
                    c3_single.mro(name))
            except RuntimeError:
                if cylc.flags.debug:
                    raise
                exc_lines = traceback.format_exc().splitlines()
                if exc_lines[-1].startswith(
                        "RuntimeError: maximum recursion depth exceeded"):
                    raise SuiteConfigError(
                        "ERROR: circular [runtime] inheritance?")
                raise

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

    def compute_inheritance(self, use_simple_method=True):
        if cylc.flags.verbose:
            OUT.info("Parsing the runtime namespace hierarchy")

        results = OrderedDictWithDefaults()
        # n_reps = 0
        already_done = {}  # to store already computed namespaces by mro

        # Loop through runtime members, 'root' first.
        nses = self.cfg['runtime'].keys()
        nses.sort(key=lambda ns: ns != 'root')
        for ns in nses:
            # for each namespace ...

            hierarchy = copy(self.runtime['linearized ancestors'][ns])
            hierarchy.reverse()

            result = OrderedDictWithDefaults()

            if use_simple_method:
                # Go up the linearized MRO from root, replicating or
                # overriding each namespace element as we go.
                for name in hierarchy:
                    replicate(result, self.cfg['runtime'][name])
                    # n_reps += 1

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
                            result = OrderedDictWithDefaults()
                            replicate(result, ad_result)  # ...and use stored
                            # n_reps += 1
                        # override name content into tmp
                        replicate(result, self.cfg['runtime'][name])
                        # n_reps += 1
                        # record this mro as already done
                        already_done[i_mro] = result

            results[ns] = result

        # replace pre-inheritance namespaces with the post-inheritance result
        self.cfg['runtime'] = results

        # uncomment this to compare the simple and efficient methods
        # print '  Number of namespace replications:', n_reps

    # def print_inheritance(self):
    #     # (use for debugging)
    #     for foo in self.runtime:
    #         log_msg = '\t' + foo
    #         for item, val in self.runtime[foo].items():
    #             log_msg += '\t\t' + item + '\t' + val
    #         OUT.info(log_msg)

    def compute_runahead_limits(self):
        """Extract the runahead limits information."""
        max_cycles = self.cfg['scheduling']['max active cycle points']
        if max_cycles == 0:
            raise SuiteConfigError(
                "ERROR: max cycle points must be greater than %s" %
                (max_cycles)
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

    def get_custom_runahead_limit(self):
        """Return the custom runahead limit (may be None)."""
        return self.custom_runahead_limit

    def get_max_num_active_cycle_points(self):
        """Return the maximum allowed number of pool cycle points."""
        return self.max_num_active_cycle_points

    def get_config(self, args, sparse=False):
        return self.pcfg.get(args, sparse)

    def adopt_orphans(self, orphans):
        # Called by the scheduler after reloading the suite definition
        # at run time and finding any live task proxies whose
        # definitions have been removed from the suite. Keep them
        # in the default queue and under the root family, until they
        # run their course and disappear.
        queues = self.cfg['scheduling']['queues']
        for orphan in orphans:
            self.runtime['linearized ancestors'][orphan] = [orphan, 'root']
            queues[self.Q_DEFAULT]['members'].append(orphan)

    def configure_queues(self):
        """Assign tasks to internal queues."""
        # Note this modifies the parsed config dict.
        queues = self.cfg['scheduling']['queues']

        if cylc.flags.verbose:
            OUT.info("Configuring internal queues")

        # First add all tasks to the default queue.
        all_task_names = self.get_task_name_list()
        queues[self.Q_DEFAULT]['members'] = all_task_names

        # Then reassign to other queues as requested.
        warnings = []
        requeued = []
        for key, queue in queues.copy().items():
            # queues.copy() is essential here to allow items to be removed from
            # the queues dict.
            if key == self.Q_DEFAULT:
                continue
            # Assign tasks to queue and remove them from default.
            qmembers = []
            for qmember in queue['members']:
                # Is a family.
                if qmember in self.runtime['descendants']:
                    # Replace with member tasks.
                    for fmem in self.runtime['descendants'][qmember]:
                        # This includes sub-families.
                        if qmember not in qmembers:
                            try:
                                queues[self.Q_DEFAULT]['members'].remove(fmem)
                            except ValueError:
                                if fmem in requeued:
                                    msg = "%s: ignoring %s from %s (%s)" % (
                                        key, fmem, qmember,
                                        'already assigned to a queue')
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
                            queues[self.Q_DEFAULT]['members'].remove(qmember)
                        except ValueError:
                            if qmember in requeued:
                                msg = "%s: ignoring '%s' (%s)" % (
                                    key, qmember, 'task already assigned')
                                warnings.append(msg)
                            elif qmember not in all_task_names:
                                msg = "%s: ignoring '%s' (%s)" % (
                                    key, qmember, 'task not defined')
                                warnings.append(msg)
                            else:
                                # Ignore: task not used in the graph.
                                pass
                        else:
                            qmembers.append(qmember)
                            requeued.append(qmember)

            if warnings:
                err_msg = "Queue configuration warnings:"
                for msg in warnings:
                    err_msg += "\n+ %s" % msg
                ERR.warning(err_msg)

            if qmembers:
                queue['members'] = qmembers
            else:
                del queues[key]

        if cylc.flags.verbose and len(queues) > 1:
            log_msg = "Internal queues created:"
            for key, queue in queues.items():
                if key == self.Q_DEFAULT:
                    continue
                log_msg += "\n+ %s: %s" % (key, ', '.join(queue['members']))
            OUT.info(log_msg)

    def configure_suite_state_polling_tasks(self):
        # Check custom script is not defined for automatic suite polling tasks.
        for l_task in self.suite_polling_tasks:
            try:
                cs = self.pcfg.getcfg(sparse=True)['runtime'][l_task]['script']
            except:
                pass
            else:
                if cs:
                    OUT.info(cs)
                    # (allow explicit blanking of inherited script)
                    raise SuiteConfigError(
                        "ERROR: script cannot be defined for automatic" +
                        " suite polling task " + l_task)
        # Generate the automatic scripting.
        for name, tdef in self.taskdefs.items():
            if name not in self.suite_polling_tasks:
                continue
            rtc = tdef.rtconfig
            comstr = "cylc suite-state" + \
                     " --task=" + tdef.suite_polling_cfg['task'] + \
                     " --point=$CYLC_TASK_CYCLE_POINT" + \
                     " --status=" + tdef.suite_polling_cfg['status']
            for key, fmt in [
                    ('user', ' --%s=%s'),
                    ('host', ' --%s=%s'),
                    ('interval', ' --%s=%d'),
                    ('max-polls', ' --%s=%s'),
                    ('run-dir', ' --%s=%s'),
                    ('template', ' --%s=%s')]:
                if rtc['suite state polling'][key]:
                    comstr += fmt % (key, rtc['suite state polling'][key])
            comstr += " " + tdef.suite_polling_cfg['suite']
            script = "echo " + comstr + "\n" + comstr
            rtc['script'] = script

    def configure_sim_modes(self):
        """Adjust task defs for simulation mode and dummy modes."""
        for tdef in self.taskdefs.values():
            # Compute simulated run time by scaling the execution limit.
            rtc = tdef.rtconfig
            limit = rtc['job']['execution time limit']
            speedup = rtc['simulation']['speedup factor']
            if limit and speedup:
                sleep_sec = (DurationParser().parse(
                    str(limit)).get_seconds() / speedup)
            else:
                sleep_sec = DurationParser().parse(
                    str(rtc['simulation']['default run length'])
                ).get_seconds()
            rtc['job']['execution time limit'] = (
                sleep_sec + DurationParser().parse(str(
                    rtc['simulation']['time limit buffer'])
                ).get_seconds())
            rtc['job']['simulated run length'] = sleep_sec

            # Generate dummy scripting.
            rtc['init-script'] = ""
            rtc['env-script'] = ""
            rtc['pre-script'] = ""
            rtc['post-script'] = ""
            scr = "sleep %d" % sleep_sec
            # Dummy message outputs.
            for msg in rtc['outputs'].values():
                scr += "\ncylc message '%s'" % msg
            if rtc['simulation']['fail try 1 only']:
                arg1 = "true"
            else:
                arg1 = "false"
            arg2 = " ".join(rtc['simulation']['fail cycle points'])
            scr += "\ncylc__job__dummy_result %s %s || exit 1" % (arg1, arg2)
            rtc['script'] = scr

            # Disable batch scheduler in dummy modes.
            # TODO - to use batch schedulers in dummy mode we need to
            # identify which resource directives to disable or modify.
            # (Only execution time limit is automatic at the moment.)
            rtc['job']['batch system'] = 'background'

            # Disable environment, in case it depends on env-script.
            rtc['environment'] = {}

            if tdef.run_mode == 'dummy-local':
                # Run all dummy tasks on the suite host.
                rtc['remote']['host'] = None
                rtc['remote']['owner'] = None

            # Simulation mode tasks should fail in which cycle points?
            f_pts = []
            f_pts_orig = rtc['simulation']['fail cycle points']
            if 'all' in f_pts_orig:
                # None for "fail all points".
                f_pts = None
            else:
                # (And [] for "fail no points".)
                for point_str in f_pts_orig:
                    f_pts.append(get_point(point_str).standardise())
            rtc['simulation']['fail cycle points'] = f_pts

    def get_parent_lists(self):
        return self.runtime['parents']

    def get_first_parent_ancestors(self, pruned=False):
        if pruned:
            # prune non-task namespaces from ancestors dict
            pruned_ancestors = {}
            for key, val in self.runtime['first-parent ancestors'].items():
                if key not in self.taskdefs:
                    continue
                pruned_ancestors[key] = val
            return pruned_ancestors
        else:
            return self.runtime['first-parent ancestors']

    def get_linearized_ancestors(self):
        return self.runtime['linearized ancestors']

    def get_first_parent_descendants(self):
        return self.runtime['first-parent descendants']

    @staticmethod
    def define_inheritance_tree(tree, hierarchy):
        """Combine inheritance hierarchies into a tree structure."""
        for rt_ in hierarchy:
            hier = copy(hierarchy[rt_])
            hier.reverse()
            cur_tree = tree
            for item in hier:
                if item not in cur_tree:
                    cur_tree[item] = {}
                cur_tree = cur_tree[item]

    def add_tree_titles(self, tree):
        for key, val in tree.items():
            if val == {}:
                if 'title' in self.cfg['runtime'][key]['meta']:
                    tree[key] = self.cfg['runtime'][key]['meta']['title']
                else:
                    tree[key] = 'No title provided'
            elif isinstance(val, dict):
                self.add_tree_titles(val)

    def get_namespace_list(self, which):
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
                    names.append(ns)
        result = {}
        for ns in names:
            if 'title' in self.cfg['runtime'][ns]['meta']:
                # the runtime dict is sparse at this stage.
                result[ns] = self.cfg['runtime'][ns]['meta']['title']
            else:
                # no need to flesh out the full runtime just for title
                result[ns] = "No title provided"

        return result

    def get_mro(self, ns):
        try:
            mro = self.runtime['linearized ancestors'][ns]
        except KeyError:
            mro = ["ERROR: no such namespace: " + ns]
        return mro

    def print_first_parent_tree(self, pretty=False, titles=False):
        # find task namespaces (no descendants)
        tasks = []
        for ns in self.cfg['runtime']:
            if ns not in self.runtime['descendants']:
                tasks.append(ns)

        pruned_ancestors = self.get_first_parent_ancestors(pruned=True)
        tree = {}
        self.define_inheritance_tree(tree, pruned_ancestors)
        padding = ''
        if titles:
            self.add_tree_titles(tree)
            # compute pre-title padding
            maxlen = 0
            for namespace in pruned_ancestors:
                items = copy(pruned_ancestors[namespace])
                items.reverse()
                for itt, item in enumerate(items):
                    tmp = 2 * itt + 1 + len(item)
                    if itt == 0:
                        tmp -= 1
                    if tmp > maxlen:
                        maxlen = tmp
            padding = maxlen * ' '

        print_tree(tree, padding=padding, use_unicode=pretty)

    def process_directories(self):
        os.environ['CYLC_SUITE_NAME'] = self.suite
        os.environ['CYLC_SUITE_DEF_PATH'] = self.fdir

    def check_tasks(self):
        """Call after all tasks are defined.

        ONLY IF VALIDATING THE SUITE
        because checking conditional triggers below may be slow for
        huge suites (several thousand tasks).
        Note:
          (a) self.cfg['runtime'][name]
              contains the task definition sections of the suite.rc file.
          (b) self.taskdefs[name]
              contains tasks that will be used, defined by the graph.
        Tasks (a) may be defined but not used (e.g. commented out of the
        graph)
        Tasks (b) may not be defined in (a), in which case they are dummied
        out.
        """

        for taskdef in self.taskdefs.values():
            try:
                taskdef.check_for_explicit_cycling()
            except TaskDefError as exc:
                raise SuiteConfigError(str(exc))
            # Check use of ksh in "[job]shell" setting
            job_shell = taskdef.rtconfig['job']['shell']
            if job_shell and 'ksh' in os.path.basename(job_shell):
                ERR.warning(
                    ('deprecated: [runtime][%s][job]shell=%s: '
                     'use of ksh to run cylc task job file') %
                    (taskdef.name, job_shell))
            # Check custom event handler templates compat with task meta
            if taskdef.rtconfig['events']:
                subs = dict((key, key) for key in self.TASK_EVENT_TMPL_KEYS)
                for key, value in self.cfg['meta'].items():
                    subs['suite_' + key.lower()] = value
                subs.update(taskdef.rtconfig['meta'])
                try:
                    subs['task_url'] = subs.pop('URL')
                except KeyError:
                    pass
                for key, values in taskdef.rtconfig['events'].items():
                    if values and (
                            key == 'handlers' or key.endswith(' handler')):
                        for value in values:
                            try:
                                value % subs
                            except (KeyError, ValueError) as exc:
                                raise SuiteConfigError(
                                    'ERROR: bad task event handler template'
                                    ' %s: %s: %s' % (
                                        taskdef.name, value, repr(exc)))
        if cylc.flags.verbose:
            OUT.info("Checking for defined tasks not used in the graph")
            for name in self.cfg['runtime']:
                if name not in self.taskdefs:
                    if name not in self.runtime['descendants']:
                        # Family triggers have been replaced with members.
                        ERR.warning(
                            'task "%s" not used in the graph.' % (name))
        # Check declared special tasks are valid.
        for task_type in self.cfg['scheduling']['special tasks']:
            for name in self.cfg['scheduling']['special tasks'][task_type]:
                if task_type in ['clock-trigger', 'clock-expire',
                                 'external-trigger']:
                    name = name.split('(', 1)[0]
                if not TaskID.is_valid_name(name):
                    raise SuiteConfigError(
                        'ERROR: Illegal %s task name: %s' % (task_type, name))
                if (name not in self.taskdefs and
                        name not in self.cfg['runtime']):
                    msg = '%s task "%s" is not defined.' % (task_type, name)
                    if self.strict:
                        raise SuiteConfigError("ERROR: " + msg)
                    else:
                        ERR.warning(msg)

    def get_task_name_list(self):
        # return a list of all tasks used in the dependency graph
        return self.taskdefs.keys()

    def generate_edges(self, lexpr, orig_lexpr, left_nodes, right, seq,
                       suicide=False):
        """Generate edges.

        Add nodes from this graph section to the abstract graph edges
        structure.
        """
        conditional = False
        if '|' in lexpr:
            # plot conditional triggers differently
            conditional = True

        if seq not in self.edges:
            self.edges[seq] = set()
        if not left_nodes:
            # Right is a lone node.
            self.edges[seq].add((right, None, suicide, conditional))

        for left in left_nodes:
            # if left is None:
            #    continue
            # TODO - RIGHT CANNOT BE NONE NOW?
            # if right is not None:
            # Check for self-edges.
            if left == right or left.startswith(right + ':'):
                # (This passes inter-cycle offsets: left[-P1D] => left)
                # (TODO - but not explicit null offsets like [-P0D]!)
                if suicide:
                    continue
                if orig_lexpr != lexpr:
                    ERR.error("%s => %s" % (orig_lexpr, right))
                raise SuiteConfigError(
                    "ERROR, self-edge detected: %s => %s" % (
                        left, right))
            self.edges[seq].add((left, right, suicide, conditional))

    def generate_taskdefs(self, orig_expr, left_nodes, right, seq):
        """Generate task definitions for all nodes in orig_expr."""

        for node in left_nodes + [right]:
            if not node:
                # if right is None, lefts are lone nodes
                # for which we still define the taskdefs
                continue
            try:
                name, offset_is_from_icp, _, offset, _ = (
                    GraphNodeParser.get_inst().parse(node))
            except GraphNodeError as exc:
                ERR.error(orig_expr)
                raise SuiteConfigError(str(exc))

            if name not in self.cfg['runtime']:
                # naked dummy task, implicit inheritance from root
                self.naked_dummy_tasks.append(name)
                # These can't just be a reference to root runtime as we have to
                # make some items task-specific: e.g. subst task name in URLs.
                self.cfg['runtime'][name] = OrderedDictWithDefaults()
                replicate(self.cfg['runtime'][name],
                          self.cfg['runtime']['root'])
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
            taskdef = self.get_taskdef(name, orig_expr)

            if name in self.suite_polling_tasks:
                taskdef.suite_polling_cfg = {
                    'suite': self.suite_polling_tasks[name][0],
                    'task': self.suite_polling_tasks[name][1],
                    'status': self.suite_polling_tasks[name][2]}

            if not offset_is_from_icp:
                if offset:
                    taskdef.used_in_offset_trigger = True
                else:
                    taskdef.add_sequence(seq)

            # Record custom message outputs.
            for item in self.cfg['runtime'][name]['outputs'].items():
                if item not in taskdef.outputs:
                    taskdef.outputs.append(item)
                    # Check for obsolete task message offsets.
                    if BCOMPAT_MSG_RE_C6.match(item[1]):
                        raise SuiteConfigError(
                            'ERROR: Message trigger offsets are obsolete.')

    def generate_triggers(self, lexpression, left_nodes, right, seq,
                          suicide, task_triggers):
        """Create Dependency and TaskTrigger objects.

        Register dependency with the relevant TaskDef object.

        """
        if not right or not left_nodes:
            # Lone nodes have no triggers.
            return

        # Convert expression to a (nested) list.
        try:
            expr_list = ConditionalSimplifier.listify(lexpression)
        except SyntaxError:
            raise SuiteConfigError('Error in expression "%s"' % lexpression)

        triggers = {}
        for left in left_nodes:
            # (GraphNodeError checked above)
            name, offset_is_from_icp, offset_is_irregular, offset, output = (
                GraphNodeParser.get_inst().parse(left))
            ltaskdef = self.taskdefs[name]

            # Determine intercycle offsets.
            abs_cycle_point = None
            cycle_point_offset = None
            if offset_is_from_icp:
                first_point = get_point_relative(offset, self.initial_point)
                last_point = seq.get_stop_point()
                abs_cycle_point = first_point
                if last_point is None:
                    # This dependency persists for the whole suite run.
                    ltaskdef.intercycle_offsets.add((None, seq))
                else:
                    ltaskdef.intercycle_offsets.add(
                        (str(first_point - last_point), seq))
            elif offset:
                if offset_is_irregular:
                    offset_tuple = (offset, seq)
                else:
                    offset_tuple = (offset, None)
                ltaskdef.intercycle_offsets.add(offset_tuple)
                cycle_point_offset = offset

            # Qualifier.
            outputs = self.cfg['runtime'][name]['outputs']
            if outputs and output in outputs:
                # Qualifier is a task message.
                qualifier = outputs[output]
            elif output:
                # Qualifier specified => standardise.
                qualifier = TaskTrigger.get_trigger_name(output)
            else:
                # No qualifier specified => use "succeeded".
                qualifier = TASK_OUTPUT_SUCCEEDED

            # Generate TaskTrigger if not already done.
            key = (name, abs_cycle_point, cycle_point_offset, qualifier)
            try:
                task_trigger = task_triggers[key]
            except KeyError:
                task_trigger = TaskTrigger(*key)
                task_triggers[key] = task_trigger

            triggers[left] = task_trigger

        # Walk down "expr_list" depth first, and replace any items matching a
        # key in "triggers" ("left" values) with the trigger.
        stack = [expr_list]
        while stack:
            item_list = stack.pop()
            for i, item in enumerate(item_list):
                if isinstance(item, list):
                    stack.append(item)
                elif item in triggers:
                    item_list[i] = triggers[item]

        dependency = Dependency(expr_list, set(triggers.values()), suicide)
        self.taskdefs[right].add_dependency(dependency, seq)

    def get_actual_first_point(self, start_point):
        """Get actual first cycle point for the suite

        Get all sequences to adjust the putative start time upward.
        """
        if (self._start_point_for_actual_first_point is not None and
                self._start_point_for_actual_first_point == start_point and
                self.actual_first_point is not None):
            return self.actual_first_point
        self._start_point_for_actual_first_point = start_point
        adjusted = []
        for seq in self.sequences:
            point = seq.get_first_point(start_point)
            if point:
                adjusted.append(point)
        if len(adjusted) > 0:
            adjusted.sort()
            self.actual_first_point = adjusted[0]
        else:
            self.actual_first_point = start_point
        return self.actual_first_point

    def get_graph_raw(self, start_point_string, stop_point_string,
                      group_nodes=None, ungroup_nodes=None,
                      ungroup_recursive=False, group_all=False,
                      ungroup_all=False, is_validate=False):
        """Convert the abstract graph edges (self.edges, etc) to actual edges

        Actual edges have concrete ranges of cycle points.

        In validate mode, set ungroup_all to True, and only return non-suicide
        edges with left and right nodes.
        """
        if is_validate:
            ungroup_all = True
        if group_nodes is None:
            group_nodes = []
        if ungroup_nodes is None:
            ungroup_nodes = []

        if self.first_graph:
            self.first_graph = False
            if not self.collapsed_families_rc and not ungroup_all:
                # initially default to collapsing all families if
                # "[visualization]collapsed families" not defined
                group_all = True

        first_parent_descendants = self.runtime['first-parent descendants']
        if group_all:
            # Group all family nodes
            if self.collapsed_families_rc:
                self.closed_families = copy(self.collapsed_families_rc)
            else:
                for fam in first_parent_descendants:
                    if fam != 'root':
                        if fam not in self.closed_families:
                            self.closed_families.append(fam)
        elif ungroup_all:
            # Ungroup all family nodes
            self.closed_families = []
        elif group_nodes:
            # Group chosen family nodes
            first_parent_ancestors = self.runtime['first-parent ancestors']
            for node in group_nodes:
                parent = first_parent_ancestors[node][1]
                if parent not in self.closed_families and parent != 'root':
                    self.closed_families.append(parent)
        elif ungroup_nodes:
            # Ungroup chosen family nodes
            for node in ungroup_nodes:
                if node not in self.runtime['descendants']:
                    # not a family node
                    continue
                if node in self.closed_families:
                    self.closed_families.remove(node)
                if ungroup_recursive:
                    for fam in copy(self.closed_families):
                        if fam in first_parent_descendants[node]:
                            self.closed_families.remove(fam)

        n_points = self.cfg['visualization']['number of cycle points']

        graph_raw_id = (
            start_point_string, stop_point_string, tuple(group_nodes),
            tuple(ungroup_nodes), ungroup_recursive, group_all,
            ungroup_all, tuple(self.closed_families),
            tuple((seq, sorted(val))
                  for seq, val in sorted(self.edges.items())),
            n_points)
        if graph_raw_id == self._last_graph_raw_id:
            return self._last_graph_raw_edges

        # Now define the concrete graph edges (pairs of nodes) for plotting.
        start_point = get_point(start_point_string)
        actual_first_point = self.get_actual_first_point(start_point)

        suite_final_point = get_point(
            self.cfg['scheduling']['final cycle point'])

        # For the computed stop point, we store n_points of each sequence,
        # and then cull later to the first n_points over all sequences.
        if stop_point_string is not None:
            stop_point = get_point(stop_point_string)
        else:
            stop_point = None

        # For nested families, only consider the outermost one
        clf_map = {}
        for name in self.closed_families:
            if all(name not in first_parent_descendants[i]
                   for i in self.closed_families):
                clf_map[name] = first_parent_descendants[name]

        gr_edges = {}
        start_point_offset_cache = {}
        point_offset_cache = None
        for sequence, edges in self.edges.items():
            # Get initial cycle point for this sequence
            point = sequence.get_first_point(start_point)
            new_points = []
            while point is not None:
                if point not in new_points:
                    new_points.append(point)
                if stop_point is not None and point > stop_point:
                    # Beyond requested final cycle point.
                    break
                if suite_final_point is not None and point > suite_final_point:
                    # Beyond suite final cycle point.
                    break
                if stop_point is None and len(new_points) > n_points:
                    # Take n_points cycles from each sequence.
                    break
                point_offset_cache = {}
                for left, right, suicide, cond in edges:
                    if is_validate and (not right or suicide):
                        continue
                    if right:
                        r_id = (right, point)
                    else:
                        r_id = None
                    name, offset_is_from_icp, _, offset, _ = (
                        GraphNodeParser.get_inst().parse(left))
                    if offset:
                        if offset_is_from_icp:
                            cache = start_point_offset_cache
                            rel_point = start_point
                        else:
                            cache = point_offset_cache
                            rel_point = point
                        try:
                            l_point = cache[offset]
                        except KeyError:
                            l_point = get_point_relative(offset, rel_point)
                            cache[offset] = l_point
                    else:
                        l_point = point
                    l_id = (name, l_point)

                    if l_id is None and r_id is None:
                        continue
                    if l_id is not None and actual_first_point > l_id[1]:
                        # Check that l_id is not earlier than start time.
                        # NOTE BUG GITHUB #919
                        # sct = start_point
                        if (r_id is None or r_id[1] < actual_first_point or
                                is_validate):
                            continue
                        # Pre-initial dependency;
                        # keep right hand node.
                        l_id = r_id
                        r_id = None
                    if point not in gr_edges:
                        gr_edges[point] = []
                    if is_validate:
                        gr_edges[point].append((l_id, r_id))
                    else:
                        lstr, rstr = self._close_families(l_id, r_id, clf_map)
                        gr_edges[point].append(
                            (lstr, rstr, None, suicide, cond))
                # Increment the cycle point.
                point = sequence.get_next_point_on_sequence(point)

        del clf_map
        del start_point_offset_cache
        del point_offset_cache
        GraphNodeParser.get_inst().clear()
        self._last_graph_raw_id = graph_raw_id
        if stop_point is None:
            # Prune to n_points points in total.
            graph_raw_edges = []
            for point in sorted(gr_edges)[:n_points]:
                graph_raw_edges.extend(gr_edges[point])
        else:
            # Flatten nested list.
            graph_raw_edges = (
                [i for sublist in gr_edges.values() for i in sublist])
        graph_raw_edges.sort()
        self._last_graph_raw_edges = graph_raw_edges
        return graph_raw_edges

    def get_node_labels(self, start_point_string, stop_point_string=None):
        """Return dependency graph node labels."""
        stop_point = None
        if stop_point_string is None:
            vfcp = self.cfg['visualization']['final cycle point']
            if vfcp:
                try:
                    stop_point = get_point_relative(
                        vfcp, get_point(start_point_string)).standardise()
                except ValueError:
                    stop_point = get_point(vfcp).standardise()

        if stop_point is not None:
            if stop_point < get_point(start_point_string):
                # Avoid a null graph.
                stop_point_string = start_point_string
            else:
                stop_point_string = str(stop_point)
        ret = set()
        for edge in self.get_graph_raw(
                start_point_string, stop_point_string, ungroup_all=True):
            left, right = edge[0:2]
            if left:
                ret.add(left)
            if right:
                ret.add(right)
        return ret

    @staticmethod
    def _close_families(l_id, r_id, clf_map):
        """Turn (name, point) to 'name.point' for edge.

        Replace close family members with family nodes if relevant.
        """
        lret = None
        lname, lpoint = None, None
        if l_id:
            lname, lpoint = l_id
            lret = TaskID.get(lname, lpoint)
        rret = None
        rname, rpoint = None, None
        if r_id:
            rname, rpoint = r_id
            rret = TaskID.get(rname, rpoint)

        for fam_name, fam_members in clf_map.items():
            if lname in fam_members and rname in fam_members:
                # l and r are both members
                lret = TaskID.get(fam_name, lpoint)
                rret = TaskID.get(fam_name, rpoint)
                break
            elif lname in fam_members:
                # l is a member
                lret = TaskID.get(fam_name, lpoint)
            elif rname in fam_members:
                # r is a member
                rret = TaskID.get(fam_name, rpoint)

        return lret, rret

    def load_graph(self):
        """Parse and load dependency graph."""
        if cylc.flags.verbose:
            OUT.info("Parsing the dependency graph")

        # Generate a map of *task* members of each family.
        # Note we could exclude 'root' from this and disallow use of 'root' in
        # the graph (which would probably be quite reasonable).
        family_map = {}
        for family, tasks in self.runtime['descendants'].iteritems():
            family_map[family] = [t for t in tasks if (
                t in self.runtime['parents'] and
                t not in self.runtime['descendants'])]

        # Move a cylc-5 non-cycling graph to an R1 section.
        non_cycling_graph = self.cfg['scheduling']['dependencies']['graph']
        if non_cycling_graph:
            section = get_sequence_cls().get_async_expr()
            self.cfg['scheduling']['dependencies'][section] = (
                OrderedDictWithDefaults())
            self.cfg['scheduling']['dependencies'][section]['graph'] = (
                non_cycling_graph)
        del self.cfg['scheduling']['dependencies']['graph']

        icp = self.cfg['scheduling']['initial cycle point']
        fcp = self.cfg['scheduling']['final cycle point']

        # Make a stack of sections and graphs [(sec1, graph1), ...]
        sections = []
        for section, sec_map in self.cfg['scheduling']['dependencies'].items():
            # Substitute initial and final cycle points.
            if not sec_map['graph']:
                # Empty section.
                continue
            if icp:
                section = section.replace("^", icp)
            elif "^" in section:
                raise SuiteConfigError("ERROR: Initial cycle point referenced"
                                       " (^) but not defined.")
            if fcp:
                section = section.replace("$", fcp)
            elif "$" in section:
                raise SuiteConfigError("ERROR: Final cycle point referenced"
                                       " ($) but not defined.")
            # If the section consists of more than one sequence, split it up.
            new_sections = RE_SEC_MULTI_SEQ.split(section)
            if len(new_sections) > 1:
                for new_section in new_sections:
                    sections.append((new_section.strip(), sec_map['graph']))
            else:
                sections.append((section, sec_map['graph']))

        # Parse and process each graph section.
        task_triggers = {}
        for section, graph in sections:
            try:
                seq = get_sequence(section, icp, fcp)
            except (AttributeError, TypeError, ValueError, CylcError) as exc:
                if cylc.flags.debug:
                    traceback.print_exc()
                msg = 'ERROR: Cannot process recurrence %s' % section
                msg += ' (initial cycle point=%s)' % icp
                msg += ' (final cycle point=%s)' % fcp
                if isinstance(exc, CylcError):
                    msg += ' %s' % str(exc)
                raise SuiteConfigError(msg)
            self.sequences.append(seq)
            parser = GraphParser(family_map, self.parameters)
            parser.parse_graph(graph)
            self.suite_polling_tasks.update(parser.suite_state_polling_tasks)
            self._proc_triggers(
                parser.triggers, parser.original, seq, task_triggers)

    def _proc_triggers(self, triggers, original, seq, task_triggers):
        """Define graph edges, taskdefs, and triggers, from graph sections."""
        for right, val in triggers.items():
            for expr, trigs in val.items():
                lefts, suicide = trigs
                orig = original[right][expr]
                self.generate_edges(expr, orig, lefts, right, seq, suicide)
                self.generate_taskdefs(orig, lefts, right, seq)
                self.generate_triggers(
                    expr, lefts, right, seq, suicide, task_triggers)

    def find_taskdefs(self, name):
        """Find TaskDef objects in family "name" or matching "name".

        Return a list of TaskDef objects which:
        * have names that glob matches "name".
        * are in a family that glob matches "name".
        """
        ret = []
        if name in self.taskdefs:
            # Match a task name
            ret.append(self.taskdefs[name])
        else:
            fams = self.get_first_parent_descendants()
            # Match a family name
            if name in fams:
                for member in fams[name]:
                    if member in self.taskdefs:
                        ret.append(self.taskdefs[member])
            else:
                # Glob match task names
                for key, taskdef in self.taskdefs.items():
                    if fnmatchcase(key, name):
                        ret.append(taskdef)
                # Glob match family names
                for key, members in fams.items():
                    if fnmatchcase(key, name):
                        for member in members:
                            if member in self.taskdefs:
                                ret.append(self.taskdefs[member])
        return ret

    def get_taskdef(self, name, orig_expr=None):
        """Return an instance of TaskDef for task name."""
        if name not in self.taskdefs:
            try:
                self.taskdefs[name] = self._get_taskdef(name)
            except TaskDefError as exc:
                if orig_expr:
                    ERR.error(orig_expr)
                raise SuiteConfigError(str(exc))
        return self.taskdefs[name]

    def _get_taskdef(self, name):
        """Get the dense task runtime."""
        # (TaskDefError caught above)

        try:
            rtcfg = self.cfg['runtime'][name]
        except KeyError:
            raise SuiteConfigError("Task not defined: %s" % name)
        # We may want to put in some handling for cases of changing the
        # initial cycle via restart (accidentally or otherwise).

        # Get the taskdef object for generating the task proxy class
        taskd = TaskDef(
            name, rtcfg, self.run_mode, self.start_point,
            self.cfg['scheduling']['spawn to max active cycle points'])

        # TODO - put all taskd.foo items in a single config dict

        if name in self.clock_offsets:
            taskd.clocktrigger_offset = self.clock_offsets[name]
        if name in self.expiration_offsets:
            taskd.expiration_offset = self.expiration_offsets[name]
        if name in self.ext_triggers:
            taskd.external_triggers.append(self.ext_triggers[name])

        taskd.sequential = (
            name in self.cfg['scheduling']['special tasks']['sequential'])

        taskd.namespace_hierarchy = list(
            reversed(self.runtime['linearized ancestors'][name]))

        if name in self.task_param_vars:
            taskd.param_var = self.task_param_vars[name]

        return taskd

    def describe(self, name):
        """Return title and description of the named task."""
        return self.taskdefs[name].describe()
