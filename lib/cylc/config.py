#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

# NOTE: OBSOLETED:
#  * OLD INITIAL TASKS (start-up and cold-start)
#  * IMPLICIT CYCLING
#  * ASYNC GRAPH IN CYCLING SUITE
#  * Ignored qualifiers on RHS, e.g. foo => FAM:succeed-all => bar
#    now must be "foo => FAM" and "FAM:succeed-all => bar".
#  * note cannot get-config retrieve an async graph anymore, it is moved to R1.
# TODO: CONSIDER OBSOLETING ALL cylc-5 syntax?
# TODO: check tutorial suites and CUG are consistent post cold-start remove.

from copy import deepcopy, copy
import re
import os
import re
import sys
import traceback

from cylc.c3mro import C3
from cylc.graph_parser import GraphParser
from cylc.param_expand import NameExpander
from cylc.cfgspec.suite import RawSuiteConfig
from cylc.cycling.loader import (get_point, get_point_relative,
                                 get_interval, get_interval_cls,
                                 get_sequence, get_sequence_cls,
                                 init_cyclers, INTEGER_CYCLING_TYPE,
                                 ISO8601_CYCLING_TYPE)
from cylc.cycling import IntervalParsingError
from cylc.envvar import check_varnames
import cylc.flags
from cylc.graphnode import graphnode, GraphNodeError
from cylc.message_output import MessageOutput
from cylc.print_tree import print_tree
from cylc.regpath import RegPath
from cylc.syntax_flags import (
    SyntaxVersion, set_syntax_version, VERSION_PREV, VERSION_NEW)
from cylc.taskdef import TaskDef, TaskDefError
from cylc.task_id import TaskID
from cylc.task_trigger import TaskTrigger
from cylc.wallclock import get_current_time_string

from isodatetime.data import Calendar
from parsec.OrderedDict import OrderedDictWithDefaults
from parsec.util import replicate


RE_SUITE_NAME_VAR = re.compile('\${?CYLC_SUITE_(REG_)?NAME}?')
RE_TASK_NAME_VAR = re.compile('\${?CYLC_TASK_NAME}?')
CLOCK_OFFSET_RE = re.compile(r'(' + TaskID.NAME_RE + r')(?:\(\s*(.+)\s*\))?')
EXT_TRIGGER_RE = re.compile('(.*)\s*\(\s*(.+)\s*\)\s*')
NUM_RUNAHEAD_SEQ_POINTS = 5  # Number of cycle points to look at per sequence.

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
    import cylc.graphing
except ImportError:
    graphing_disabled = True
else:
    graphing_disabled = False


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


class TaskNotDefinedError(SuiteConfigError):
    """A named task not defined."""

    def __str__(self):
        return "Task not defined: %s" % self.msg

# TODO: separate config for run and non-run purposes?


class SuiteConfig(object):
    """Class for suite configuration items and derived quantities."""

    _INSTANCE = None
    _FORCE = False  # Override singleton behaviour (only used by "cylc diff"!)

    @classmethod
    def get_inst(cls, suite=None, fpath=None, template_vars=None,
                 owner=None, run_mode='live', validation=False, strict=False,
                 collapsed=[], cli_initial_point_string=None,
                 cli_start_point_string=None, cli_final_point_string=None,
                 is_restart=False, is_reload=False, write_proc=True,
                 vis_start_string=None, vis_stop_string=None,
                 mem_log_func=None):
        """Return a singleton instance.

        On 1st call, instantiate the singleton.
        Argument list is only relevant on 1st call.

        """
        if cls._INSTANCE is None or cls._FORCE:
            cls._FORCE = False
            cls._INSTANCE = cls(
                suite, fpath, template_vars, owner,
                run_mode, validation, strict, collapsed,
                cli_initial_point_string, cli_start_point_string,
                cli_final_point_string, is_restart, is_reload, write_proc,
                vis_start_string, vis_stop_string, mem_log_func)
        return cls._INSTANCE

    def __init__(self, suite, fpath, template_vars=None,
                 owner=None, run_mode='live', validation=False, strict=False,
                 collapsed=[], cli_initial_point_string=None,
                 cli_start_point_string=None, cli_final_point_string=None,
                 is_restart=False, is_reload=False, write_proc=True,
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
        self.edges = []
        self.taskdefs = {}
        self.validation = validation
        self.initial_point = None
        self.start_point = None
        self.is_restart = is_restart
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
        self.mem_log("config.py: before RawSuiteConfig.get_inst")
        self.pcfg = RawSuiteConfig.get_inst(
            fpath, force=is_reload, tvars=template_vars, write_proc=write_proc)
        self.mem_log("config.py: after RawSuiteConfig.get_inst")
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
                    raise SuiteConfigError(
                        'Conflicting syntax: integer vs ' +
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
            print "Expanding [runtime] namespace lists and parameters"

        # Set default parameter expansion templates if necessary.
        for pname, pvalues in parameter_values.items():
            if pname not in parameter_templates:
                try:
                    [int(i) for i in pvalues]
                except ValueError:
                    # Don't prefix string values with the parameter name.
                    parameter_templates[pname] = "_%(" + pname + ")s"
                else:
                    # All int values, prefix values with the parameter name.
                    parameter_templates[pname] = (
                        "_" + pname + "%(" + pname + ")s")

        # This requires expansion into a new OrderedDict to preserve the
        # correct order of the final list of namespaces (add-or-override
        # by repeated namespace depends on this).
        newruntime = OrderedDictWithDefaults()
        name_expander = NameExpander(self.parameters)
        for namespace_heading, namespace_dict in self.cfg['runtime'].items():
            for name, indices in name_expander.expand(namespace_heading):
                if name not in newruntime:
                    newruntime[name] = OrderedDictWithDefaults()
                # Put parameter index values in task environment.
                replicate(newruntime[name], namespace_dict)
                if indices:
                    if 'environment' not in newruntime[name]:
                        newruntime[name]['environment'] = (
                            OrderedDictWithDefaults())
                    for p_name, p_val in indices.items():
                        p_var_name = 'CYLC_TASK_PARAM_%s' % p_name
                        newruntime[name]['environment'][p_var_name] = p_val
                    if 'inherit' in newruntime[name]:
                        parents = newruntime[name]['inherit']
                        origin = 'inherit = %s' % ' '.join(parents)
                        repl_parents = []
                        for parent in parents:
                            repl_parents.append(name_expander.replace_params(
                                parent, indices, origin))
                        newruntime[name]['inherit'] = repl_parents
        self.cfg['runtime'] = newruntime

        # Parameter expansion of visualization node attributes.
        # TODO - 'node groups' should really have this too, but I'd rather
        # deprecate them (just use families for visualization groups now).
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

        self.ns_defn_order = newruntime.keys()

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
            print "Parsing [special tasks]"
        for type in self.cfg['scheduling']['special tasks']:
            result = copy(self.cfg['scheduling']['special tasks'][type])
            extn = ''
            for item in self.cfg['scheduling']['special tasks'][type]:
                name = item
                if type == 'external-trigger':
                    m = re.match(EXT_TRIGGER_RE, item)
                    if m is None:
                        raise SuiteConfigError(
                            "ERROR: Illegal %s spec: %s" % (type, item)
                        )
                    name, ext_trigger_msg = m.groups()
                    extn = "(" + ext_trigger_msg + ")"

                elif type in ['clock-trigger', 'clock-expire']:
                    m = re.match(CLOCK_OFFSET_RE, item)
                    if m is None:
                        raise SuiteConfigError(
                            "ERROR: Illegal %s spec: %s" % (type, item)
                        )
                    if (self.cfg['scheduling']['cycling mode'] !=
                            Calendar.MODE_GREGORIAN):
                        raise SuiteConfigError(
                            "ERROR: %s tasks require "
                            "[scheduling]cycling mode=%s" % (
                                type, Calendar.MODE_GREGORIAN)
                        )
                    name, offset_string = m.groups()
                    if not offset_string:
                        offset_string = "PT0M"
                    if cylc.flags.verbose:
                        if offset_string.startswith("-"):
                            print >> sys.stderr, (
                                "WARNING: %s offsets are "
                                "normally positive: %s" % (type, item))
                    offset_converted_from_prev = False
                    try:
                        float(offset_string)
                    except ValueError:
                        # So the offset should be an ISO8601 interval.
                        pass
                    else:
                        # Backward-compatibility for a raw float number of
                        # hours.
                        set_syntax_version(
                            VERSION_PREV,
                            "%s=%s: integer offset" % (type, item)
                        )
                        if (get_interval_cls().get_null().TYPE ==
                                ISO8601_CYCLING_TYPE):
                            seconds = int(float(offset_string) * 3600)
                            offset_string = "PT%sS" % seconds
                        offset_converted_from_prev = True
                    try:
                        offset_interval = (
                            get_interval(offset_string).standardise())
                    except IntervalParsingError as exc:
                        raise SuiteConfigError(
                            "ERROR: Illegal %s spec: %s" % (
                                type, offset_string))
                    else:
                        if not offset_converted_from_prev:
                            set_syntax_version(
                                VERSION_NEW,
                                "%s=%s: ISO 8601 offset" % (type, item)
                            )
                    extn = "(" + offset_string + ")"

                # Replace family names with members.
                if name in self.runtime['descendants']:
                    result.remove(item)
                    for member in self.runtime['descendants'][name]:
                        if member in self.runtime['descendants']:
                            # (sub-family)
                            continue
                        result.append(member + extn)
                        if type == 'clock-trigger':
                            self.clock_offsets[member] = offset_interval
                        if type == 'clock-expire':
                            self.expiration_offsets[member] = offset_interval
                        if type == 'external-trigger':
                            self.ext_triggers[member] = ext_trigger_msg
                elif type == 'clock-trigger':
                    self.clock_offsets[name] = offset_interval
                elif type == 'clock-expire':
                    self.expiration_offsets[name] = offset_interval
                elif type == 'external-trigger':
                    self.ext_triggers[name] = self.dequote(ext_trigger_msg)

            self.cfg['scheduling']['special tasks'][type] = result

        self.collapsed_families_rc = (
            self.cfg['visualization']['collapsed families'])
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
                self.closed_families.remove(cfam)
                if fromrc and cylc.flags.verbose:
                    print >> sys.stderr, (
                        'WARNING, [visualization][collapsed families]: ' +
                        'family ' + cfam + ' not defined')

        # check for run mode override at suite level
        if self.cfg['cylc']['force run mode']:
            self.run_mode = self.cfg['cylc']['force run mode']

        self.process_directories()

        self.mem_log("config.py: before load_graph()")
        self.load_graph()
        self.mem_log("config.py: after load_graph()")

        self.compute_runahead_limits()

        self.configure_queues()

        # Warn or abort (if --strict) if naked dummy tasks (no runtime
        # section) are found in graph or queue config.
        if len(self.naked_dummy_tasks) > 0:
            if self.strict or cylc.flags.verbose:
                print >> sys.stderr, (
                    'WARNING: naked dummy tasks detected (no entry under ' +
                    '[runtime]):')
                for ndt in self.naked_dummy_tasks:
                    print >> sys.stderr, '  +', ndt
            if self.strict:
                raise SuiteConfigError(
                    'ERROR: strict validation fails naked dummy tasks')

        if self.validation:
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
                    print >> sys.stderr, (
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
            print "Checking [visualization] node attributes"
            # TODO - these should probably be done in non-verbose mode too.
            # 1. node groups should contain valid namespace names
            nspaces = self.cfg['runtime'].keys()
            bad = {}
            for ng, mems in ngs.items():
                n_bad = []
                for m in mems:
                    if m not in nspaces:
                        n_bad.append(m)
                if n_bad:
                    bad[ng] = n_bad
            if bad:
                print >> sys.stderr, "  WARNING: undefined node group members"
                for ng, mems in bad.items():
                    print >> sys.stderr, " + " + ng + ":", ','.join(mems)

            # 2. node attributes must refer to node groups or namespaces
            bad = []
            for na in self.cfg['visualization']['node attributes']:
                if na not in ngs and na not in nspaces:
                    bad.append(na)
            if bad:
                print >> sys.stderr, (
                    "  WARNING: undefined node attribute targets")
                for na in bad:
                    print >> sys.stderr, " + " + na

        # 3. node attributes must be lists of quoted "key=value" pairs.
        fail = False
        for node, attrs in (
                self.cfg['visualization']['node attributes'].items()):
            for attr in attrs:
                try:
                    key, value = re.split('\s*=\s*', attr)
                except ValueError as exc:
                    fail = True
                    print >> sys.stderr, (
                        "ERROR: [visualization][node attributes]%s = %s" % (
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
        for ns, ancestors in self.runtime['first-parent ancestors'].items():
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
                    print >> sys.stderr, (
                        "WARNING: ignoring [visualization]final cycle point\n"
                        "  (it must be defined with an initial cycle point)")
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
        url = self.cfg['URL']
        if url is not '':
            self.cfg['URL'] = re.sub(RE_SUITE_NAME_VAR, self.suite, url)

        # Replace suite and task name in task URLs.
        for name, cfg in self.cfg['runtime'].items():
            if cfg['URL']:
                cfg['URL'] = re.sub(RE_TASK_NAME_VAR, name, cfg['URL'])
                cfg['URL'] = re.sub(RE_SUITE_NAME_VAR, self.suite, cfg['URL'])

        if self.validation:
            if graphing_disabled:
                print >> sys.stderr, (
                    "WARNING: skipping cyclic dependence check"
                    "  (could not import graphviz library)")
            else:
                # Detect cyclic dependence.
                # (ignore suicide triggers as they look like cyclic dependence:
                #    "foo:fail => bar => !foo" looks like "foo => bar => foo").
                graph = self.get_graph(ungroup_all=True, ignore_suicide=True)
                # Original edges.
                o_edges = graph.edges()
                # Reverse any back edges using graphviz 'acyclic'.
                # (Note: use of acyclic(copy=True) reveals our CGraph class
                # init should have the same arg list as its parent,
                # pygraphviz.AGraph).
                graph.acyclic()
                # Look for reversed edges (note this does not detect
                # self-edges).
                n_edges = set(graph.edges())

                back_edges = [x for x in o_edges if x not in n_edges]
                if len(back_edges) > 0:
                    print >> sys.stderr, "Back-edges:"
                    for e in back_edges:
                        print >> sys.stderr, '  %s => %s' % e
                    raise SuiteConfigError(
                        'ERROR: cyclic dependence detected '
                        '(graph the suite to see back-edges).')

        self.mem_log("config.py: end init config")

    def is_graph_defined(self, dependency_map):
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

    def dequote(self, s):
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
            print >> sys.stderr, "ERROR, bad env variable names:"
            for label, vars in bad.items():
                print >> sys.stderr, 'Namespace:', label
                for var in vars:
                    print >> sys.stderr, "  ", var
            raise SuiteConfigError(
                "Illegal environment variable name(s) detected")

    def filter_env(self):
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
            print "First parent(s) demoted to secondary:"
            for n, p in demoted.items():
                print " +", p, "as parent of '" + n + "'"

        c3 = C3(self.runtime['parents'])
        c3_single = C3(first_parents)

        for name in self.cfg['runtime']:
            try:
                self.runtime['linearized ancestors'][name] = c3.mro(name)
                self.runtime['first-parent ancestors'][name] = (
                    c3_single.mro(name))
            except RuntimeError as exc:
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

        # for name in self.cfg['runtime']:
        #     print name, self.runtime['linearized ancestors'][name]

    def compute_inheritance(self, use_simple_method=True):
        if cylc.flags.verbose:
            print "Parsing the runtime namespace hierarchy"

        results = OrderedDictWithDefaults()
        n_reps = 0

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
                            result = OrderedDictWithDefaults()
                            replicate(result, ad_result)  # ...and use stored
                            n_reps += 1
                        # override name content into tmp
                        replicate(result, self.cfg['runtime'][name])
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
            queues['default']['members'].append(orphan)

    def configure_queues(self):
        """Assign tasks to internal queues."""
        # Note this modifies the parsed config dict.
        queues = self.cfg['scheduling']['queues']

        if cylc.flags.verbose:
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
                                    msg = "%s: ignoring %s from %s (%s)" % (
                                        queue, fmem, qmember,
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
                            queues['default']['members'].remove(qmember)
                        except ValueError:
                            if qmember in requeued:
                                msg = "%s: ignoring '%s' (%s)" % (
                                    queue, qmember, 'task already assigned')
                                warnings.append(msg)
                            elif qmember not in all_task_names:
                                msg = "%s: ignoring '%s' (%s)" % (
                                    queue, qmember, 'task not defined')
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

        if cylc.flags.verbose and len(queues.keys()) > 1:
            print "Internal queues created:"
            for queue in queues:
                if queue == 'default':
                    continue
                print "  + %s: %s" % (
                    queue, ', '.join(queues[queue]['members']))

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

    def define_inheritance_tree(self, tree, hierarchy, titles=False):
        # combine inheritance hierarchies into a tree structure.
        for rt in hierarchy:
            hier = copy(hierarchy[rt])
            hier.reverse()
            foo = tree
            for item in hier:
                if item not in foo:
                    foo[item] = {}
                foo = foo[item]

    def add_tree_titles(self, tree):
        for key, val in tree.items():
            if val == {}:
                if 'title' in self.cfg['runtime'][key]:
                    tree[key] = self.cfg['runtime'][key]['title']
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
            if 'title' in self.cfg['runtime'][ns]:
                # the runtime dict is sparse at this stage.
                result[ns] = self.cfg['runtime'][ns]['title']
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
        self.define_inheritance_tree(tree, pruned_ancestors, titles=titles)
        padding = ''
        if titles:
            self.add_tree_titles(tree)
            # compute pre-title padding
            maxlen = 0
            for ns in pruned_ancestors:
                items = copy(pruned_ancestors[ns])
                items.reverse()
                for i in range(len(items)):
                    tmp = 2 * i + 1 + len(items[i])
                    if i == 0:
                        tmp -= 1
                    if tmp > maxlen:
                        maxlen = tmp
            padding = maxlen * ' '

        print_tree(tree, padding=padding, use_unicode=pretty)

    def process_directories(self):
        os.environ['CYLC_SUITE_NAME'] = self.suite
        os.environ['CYLC_SUITE_REG_PATH'] = RegPath(self.suite).get_fpath()
        os.environ['CYLC_SUITE_DEF_PATH'] = self.fdir

    def check_tasks(self):
        # Call after all tasks are defined.
        # ONLY IF VALIDATING THE SUITE
        # because checking conditional triggers below may be slow for
        # huge suites (several thousand tasks).
        # Note:
        #   (a) self.cfg['runtime'][name]
        #       contains the task definition sections of the suite.rc file.
        #   (b) self.taskdefs[name]
        #       contains tasks that will be used, defined by the graph.
        # Tasks (a) may be defined but not used (e.g. commented out of the
        # graph)
        # Tasks (b) may not be defined in (a), in which case they are dummied
        # out.

        for taskdef in self.taskdefs.values():
            try:
                taskdef.check_for_explicit_cycling()
            except TaskDefError as exc:
                raise SuiteConfigError(str(exc))

        if cylc.flags.verbose:
            print "Checking for defined tasks not used in the graph"
            for name in self.cfg['runtime']:
                if name not in self.taskdefs:
                    if name not in self.runtime['descendants']:
                        # Family triggers have been replaced with members.
                        print >> sys.stderr, (
                            '  WARNING: task "%s" not used in the graph.' % (
                                name))
        # Check declared special tasks are valid.
        for task_type in self.cfg['scheduling']['special tasks']:
            for name in self.cfg['scheduling']['special tasks'][task_type]:
                if task_type in ['clock-trigger', 'clock-expire',
                                 'external-trigger']:
                    name = re.sub('\(.*\)', '', name)
                if not TaskID.is_valid_name(name):
                    raise SuiteConfigError(
                        'ERROR: Illegal %s task name: %s' % (task_type, name))
                if (name not in self.taskdefs and
                        name not in self.cfg['runtime']):
                    msg = '%s task "%s" is not defined.' % (task_type, name)
                    if self.strict:
                        raise SuiteConfigError("ERROR: " + msg)
                    else:
                        print >> sys.stderr, "WARNING: " + msg

        # Check custom script is not defined for automatic suite polling tasks
        for l_task in self.suite_polling_tasks:
            try:
                cs = self.pcfg.getcfg(sparse=True)['runtime'][l_task]['script']
            except:
                pass
            else:
                if cs:
                    print cs
                    # (allow explicit blanking of inherited script)
                    raise SuiteConfigError(
                        "ERROR: script cannot be defined for automatic" +
                        " suite polling task " + l_task)

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

        if not left_nodes:
            # Right is a lone node.
            # TODO - CAN WE DO THIS MORE SENSIBLY (e.g. put loner as left?)
            self.edges.append(
                cylc.graphing.edge(right, None, seq, suicide, conditional))

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
                    print >> sys.stderr, (
                        "%s => %s" % (orig_lexpr, right))
                raise SuiteConfigError(
                    "ERROR, self-edge detected: %s => %s" % (
                        left, right))
            self.edges.append(
                cylc.graphing.edge(left, right, seq, suicide, conditional))

    def generate_taskdefs(self, orig_expr, left_nodes, right, section, seq,
                          base_interval):
        """Generate task definitions for all nodes in orig_expr."""

        for node in left_nodes + [right]:
            if not node:
                # if right is None, lefts are lone nodes
                # for which we still define the taskdefs
                continue
            try:
                my_taskdef_node = graphnode(node, base_interval=base_interval)
            except GraphNodeError, x:
                print >> sys.stderr, orig_expr
                raise SuiteConfigError(str(x))

            name = my_taskdef_node.name
            offset_string = my_taskdef_node.offset_string

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
            if name not in self.taskdefs:
                try:
                    self.taskdefs[name] = self.get_taskdef(name)
                except TaskDefError as exc:
                    print >> sys.stderr, orig_expr
                    raise SuiteConfigError(str(exc))

            if name in self.suite_polling_tasks:
                self.taskdefs[name].suite_polling_cfg = {
                    'suite': self.suite_polling_tasks[name][0],
                    'task': self.suite_polling_tasks[name][1],
                    'status': self.suite_polling_tasks[name][2]}

            if not my_taskdef_node.is_absolute:
                if offset_string:
                    self.taskdefs[name].used_in_offset_trigger = True
                else:
                    self.taskdefs[name].add_sequence(seq)

            # Record custom message outputs, and generate scripting to fake
            # their completion in dummy mode.
            dm_scrpt = self.taskdefs[name].rtconfig['dummy mode']['script']
            for msg in self.cfg['runtime'][name]['outputs'].values():
                outp = MessageOutput(msg, base_interval)
                if outp not in self.taskdefs[name].outputs:
                    self.taskdefs[name].outputs.append(outp)
                    dm_scrpt += "\nsleep 2; cylc message '%s'" % msg
                self.taskdefs[name].rtconfig['dummy mode']['script'] = dm_scrpt

    def generate_triggers(self, lexpression, left_nodes,
                          right, seq, suicide, base_interval):
        if not right or not left_nodes:
            # Lone nodes have no triggers.
            return

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

            trig = TaskTrigger(
                lnode.name, lnode.output, lnode.offset_string, cycle_point,
                suicide, self.cfg['runtime'][lnode.name]['outputs'],
                base_interval)

            # Use fully qualified name for trigger expression label
            # (task name is not unique, e.g.: "F | F:fail => G").
            label = self.get_conditional_label(left)
            ctrig[label] = trig
            cname[label] = lnode.name

        expr = self.get_conditional_label(lexpression)
        self.taskdefs[right].add_trigger(ctrig, expr, seq)

    def get_actual_first_point(self, start_point):
        # Get actual first cycle point for the suite (get all
        # sequences to adjust the putative start time upward)
        if (self._start_point_for_actual_first_point is not None and
                self._start_point_for_actual_first_point == start_point and
                self.actual_first_point is not None):
            return self.actual_first_point
        self._start_point_for_actual_first_point = start_point
        adjusted = []
        for seq in self.sequences:
            foo = seq.get_first_point(start_point)
            if foo:
                adjusted.append(foo)
        if len(adjusted) > 0:
            adjusted.sort()
            self.actual_first_point = adjusted[0]
        else:
            self.actual_first_point = start_point
        return self.actual_first_point

    def get_conditional_label(self, expression):
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

    def get_graph_raw(self, start_point_string, stop_point_string,
                      group_nodes=[], ungroup_nodes=[],
                      ungroup_recursive=False, group_all=False,
                      ungroup_all=False):
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
                            self.closed_families.append(fam)
        elif ungroup_all:
            # Ungroup all family nodes
            self.closed_families = []
        elif len(group_nodes) > 0:
            # Group chosen family nodes
            for node in group_nodes:
                parent = hierarchy[node][1]
                if parent not in self.closed_families:
                    if parent != 'root':
                        self.closed_families.append(parent)
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

        n_points = self.cfg['visualization']['number of cycle points']

        graph_id = (start_point_string, stop_point_string, set(group_nodes),
                    set(ungroup_nodes), ungroup_recursive, group_all,
                    ungroup_all, set(self.closed_families),
                    set(self.edges), n_points)
        if graph_id == self._last_graph_raw_id:
            return self._last_graph_raw_edges

        # Now define the concrete graph edges (pairs of nodes) for plotting.
        gr_edges = {}
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
                if suite_final_point is not None and point > suite_final_point:
                    # Beyond suite final cycle point.
                    break
                if stop_point is None and len(new_points) > n_points:
                    # Take n_points cycles from each sequence.
                    break

                r_id = e.get_right(point, start_point)
                l_id = e.get_left(
                    point, start_point, e.sequence.get_interval())

                action = True
                if l_id is None and r_id is None:
                    # Nothing to add to the graph.
                    action = False
                if l_id is not None:
                    # Check that l_id is not earlier than start time.
                    tmp, lpoint_string = TaskID.split(l_id)
                    # NOTE BUG GITHUB #919
                    # sct = start_point
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
                    gr_edges[point].append(
                        (nl, nr, None, e.suicide, e.conditional))
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

        self._last_graph_raw_id = graph_id
        self._last_graph_raw_edges = edges
        return edges

    def get_graph(self, start_point_string=None, stop_point_string=None,
                  group_nodes=[], ungroup_nodes=[], ungroup_recursive=False,
                  group_all=False, ungroup_all=False, ignore_suicide=False,
                  subgraphs_on=False):

        # If graph extent is not given, use visualization settings.
        if start_point_string is None:
            start_point_string = (
                self.cfg['visualization']['initial cycle point'])

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
        graph = cylc.graphing.CGraph(
            self.suite, self.suite_polling_tasks, self.cfg['visualization'])
        graph.add_edges(gr_edges, ignore_suicide)
        if subgraphs_on:
            graph.add_cycle_point_subgraphs(gr_edges)
        return graph

    def get_node_labels(self, start_point_string, stop_point_string):
        graph = self.get_graph(start_point_string, stop_point_string,
                               ungroup_all=True)
        return [i.attr['label'].replace('\\n', '.') for i in graph.nodes()]

    def close_families(self, nlid, nrid):
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
        clf = copy(self.closed_families)
        for i in self.closed_families:
            for j in self.closed_families:
                if i in members[j]:
                    # i is a member of j
                    if i in clf:
                        clf.remove(i)

        for fam in clf:
            if lname in members[fam] and rname in members[fam]:
                # l and r are both members of fam
                # nl, nr = None, None
                # this makes 'the graph disappear if grouping 'root'
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
        if cylc.flags.verbose:
            print "Parsing the dependency graph"

        # Generate a map of *task* members of each family.
        # Note we could exclude 'root' from this and disallow use of 'root' in
        # the graph (which would probably be quite reasonable).
        family_map = {}
        runtime_families = self.runtime['descendants'].keys()
        runtime_tasks = [
            t for t in self.runtime['parents'].keys()
            if t not in runtime_families]
        for fam in runtime_families:
            desc = self.runtime['descendants'][fam]
            family_map[fam] = [t for t in desc if t in runtime_tasks]

        # Move a non-cycling graph to an R1 section.
        # TODO - CHECK FOR ONLY CYCLING OR NON-CYCLING GRAPH.
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
        initial_point = get_point(icp)

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
            if re.search("(?![^(]+\)),", section):
                new_sections = re.split("(?![^(]+\)),", section)
                for new_section in new_sections:
                    sections.append((new_section.strip(), sec_map['graph']))
            else:
                sections.append((section, sec_map['graph']))

        for section, graph in sections:
            seq = get_sequence(section,
                               self.cfg['scheduling']['initial cycle point'],
                               self.cfg['scheduling']['final cycle point'])
            base_interval = seq.get_interval()
            gp = GraphParser(family_map, self.parameters)
            self.sequences.append(seq)

            gp.parse_graph(graph)
            self.suite_polling_tasks.update(gp.suite_state_polling_tasks)

            for right, val in gp.triggers.items():
                for expr, trigs in val.items():
                    lefts, suicide = trigs
                    orig_expr = gp.original[right][expr]
                    if not graphing_disabled:
                        self.generate_edges(expr, orig_expr, lefts,
                                            right, seq, suicide)
                    self.generate_taskdefs(
                        orig_expr, lefts, right, section, seq, base_interval)
                    self.generate_triggers(
                        expr, lefts, right, seq, suicide, base_interval)

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

        foo = copy(self.runtime['linearized ancestors'][name])
        foo.reverse()
        taskd.namespace_hierarchy = foo

        return taskd

    def describe(self, name):
        """Return title and description of the named task."""
        return self.taskdefs[name].describe()
