#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

Set local values of variables to give suite context before parsing
config, i.e for template filters (Jinja2, python ...etc) and possibly
needed locally by event handlers. This is needed for both running and
non-running suite parsing (obtaining config/graph info). Potentially
task-specific due to different directory paths on different task hosts,
however, they are overridden by tasks prior to job submission.

Do some consistency checking, then construct task proxy objects and graph
structures.
"""


from copy import copy
from fnmatch import fnmatchcase
import os
import re
import traceback

from isodatetime.data import Calendar
from isodatetime.parsers import DurationParser
from parsec.OrderedDict import OrderedDictWithDefaults
from parsec.util import replicate

from cylc import LOG
from cylc.c3mro import C3
from cylc.conditional_simplifier import ConditionalSimplifier
from cylc.exceptions import (
    CylcError, SuiteConfigError, IntervalParsingError, TaskDefError)
from cylc.graph_parser import GraphParser
from cylc.param_expand import NameExpander
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.cfgspec.suite import RawSuiteConfig
from cylc.cycling.loader import (
    get_point, get_point_relative, get_interval, get_interval_cls,
    get_sequence, get_sequence_cls, init_cyclers, INTEGER_CYCLING_TYPE,
    ISO8601_CYCLING_TYPE)
from cylc.cycling.iso8601 import ingest_time
import cylc.flags
from cylc.graphnode import GraphNodeParser
from cylc.print_tree import print_tree
from cylc.subprocctx import SubFuncContext
from cylc.subprocpool import get_func
from cylc.suite_srv_files_mgr import SuiteSrvFilesManager
from cylc.taskdef import TaskDef
from cylc.task_id import TaskID
from cylc.task_outputs import TASK_OUTPUT_SUCCEEDED
from cylc.task_trigger import TaskTrigger, Dependency
from cylc.wallclock import get_current_time_string, set_utc_mode, get_utc_mode
from cylc.xtrigger_mgr import XtriggerManager


RE_CLOCK_OFFSET = re.compile(r'(' + TaskID.NAME_RE + r')(?:\(\s*(.+)\s*\))?')
RE_EXT_TRIGGER = re.compile(r'(.*)\s*\(\s*(.+)\s*\)\s*')
RE_SEC_MULTI_SEQ = re.compile(r'(?![^(]+\)),')
RE_SUITE_NAME_VAR = re.compile(r'\${?CYLC_SUITE_(REG_)?NAME}?')
RE_TASK_NAME_VAR = re.compile(r'\${?CYLC_TASK_NAME}?')

# Message trigger offset regex.
BCOMPAT_MSG_RE_C6 = re.compile(r'^(.*)\[\s*(([+-])?\s*(.*))?\s*\](.*)$')


def check_varnames(env):
    """Check a list of env var names for legality.

    Return a list of bad names (empty implies success).
    """
    bad = []
    for varname in env:
        if not re.match(r'^[a-zA-Z_][\w]*$', varname):
            bad.append(varname)
    return bad

# TODO: separate config for run and non-run purposes?


class SuiteConfig(object):
    """Class for suite configuration items and derived quantities."""

    Q_DEFAULT = 'default'
    TASK_EVENT_TMPL_KEYS = (
        'event', 'suite', 'suite_uuid', 'point', 'name', 'submit_num', 'id',
        'message', 'batch_sys_name', 'batch_sys_job_id', 'submit_time',
        'start_time', 'finish_time', 'user@host', 'try_num')

    def __init__(self, suite, fpath, template_vars=None,
                 owner=None, run_mode='live', is_validate=False, strict=False,
                 collapsed=None, cli_initial_point_string=None,
                 cli_start_point_string=None, cli_final_point_string=None,
                 is_reload=False, output_fname=None,
                 vis_start_string=None, vis_stop_string=None,
                 xtrigger_mgr=None, mem_log_func=None,
                 run_dir=None, log_dir=None,
                 work_dir=None, share_dir=None):

        self.mem_log = mem_log_func
        if mem_log_func is None:
            self.mem_log = lambda *a: False
        self.mem_log("config.py:config.py: start init config")
        self.suite = suite  # suite name
        self.fpath = fpath  # suite definition
        self.fdir = os.path.dirname(fpath)
        self.run_dir = run_dir or glbl_cfg().get_derived_host_item(
            self.suite, 'suite run directory')
        self.log_dir = log_dir or glbl_cfg().get_derived_host_item(
            self.suite, 'suite log directory')
        self.work_dir = work_dir or glbl_cfg().get_derived_host_item(
            self.suite, 'suite work directory')
        self.share_dir = share_dir or glbl_cfg().get_derived_host_item(
            self.suite, 'suite share directory')
        self.owner = owner
        self.run_mode = run_mode
        self.strict = strict
        self.naked_dummy_tasks = []
        self.edges = {}
        self.taskdefs = {}
        self.initial_point = None
        self.start_point = None
        self.final_point = None
        self.first_graph = True
        self.clock_offsets = {}
        self.expiration_offsets = {}
        # Old external triggers (client/server)
        self.ext_triggers = {}
        if xtrigger_mgr is None:
            # For validation and graph etc.
            self.xtrigger_mgr = XtriggerManager(self.suite, self.owner)
        else:
            self.xtrigger_mgr = xtrigger_mgr
        self.xtriggers = {}
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

        # Export local environmental suite context before config parsing.
        self.process_suite_env()

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
            raise SuiteConfigError("missing [scheduling] section.")
        if 'dependencies' not in self.cfg['scheduling']:
            raise SuiteConfigError(
                "missing [scheduling][[dependencies]] section.")
        # (The check that 'graph' is defined is below).
        # The two runahead limiting schemes are mutually exclusive.
        rlim = self.cfg['scheduling'].get('runahead limit')
        mact = self.cfg['scheduling'].get('max active cycle points')
        if rlim and mact:
            raise SuiteConfigError(
                "use 'runahead limit' OR "
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

        LOG.debug("Expanding [runtime] namespace lists and parameters")

        # Set default parameter expansion templates if necessary.
        for pname, pvalues in parameter_values.items():
            if pvalues and pname not in parameter_templates:
                if any(not isinstance(pvalue, int) for pvalue in pvalues):
                    # Strings, bare parameter values
                    parameter_templates[pname] = r'_%%(%s)s' % pname
                elif any(pvalue < 0 for pvalue in pvalues):
                    # Integers, with negative value(s)
                    # Prefix values with signs and parameter names
                    parameter_templates[pname] = r'_%s%%(%s)+0%dd' % (
                        pname, pname,
                        max(len(str(pvalue)) for pvalue in pvalues))
                else:
                    # Integers, positive only
                    # Prefix values with parameter names
                    parameter_templates[pname] = r'_%s%%(%s)0%dd' % (
                        pname, pname, len(str(max(pvalues))))

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

        # Check environment variable names and parameter environment templates
        # Done before inheritance to avoid repetition
        self.check_env_names()
        self.check_param_env_tmpls()
        self.mem_log("config.py: before _expand_runtime")
        self._expand_runtime()
        self.mem_log("config.py: after _expand_runtime")

        self.ns_defn_order = list(self.cfg['runtime'])

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
        if self.cfg['cylc']['UTC mode'] is None:
            set_utc_mode(glbl_cfg().get(['cylc', 'UTC mode']))
        else:
            set_utc_mode(self.cfg['cylc']['UTC mode'])

        # Initial point from suite definition (or CLI override above).
        icp = self.cfg['scheduling']['initial cycle point']
        if icp is None:
            raise SuiteConfigError(
                "This suite requires an initial cycle point.")
        if icp == "now":
            icp = get_current_time_string()
        else:
            try:
                my_now = get_current_time_string()
                icp = ingest_time(icp, my_now)
            except ValueError as exc:
                raise SuiteConfigError(str(exc))
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
                     "%s") % (str(self.initial_point), constraints_str)
                )

        if (self.cfg['scheduling']['final cycle point'] is not None and
                self.cfg['scheduling']['final cycle point'].strip() is ""):
            self.cfg['scheduling']['final cycle point'] = None
        final_point_string = (cli_final_point_string or
                              self.cfg['scheduling']['final cycle point'])
        if final_point_string is not None:
            # Is the final "point"(/interval) relative to initial?
            if get_interval_cls().get_null().TYPE == INTEGER_CYCLING_TYPE:
                if "P" in final_point_string:
                    # Relative, integer cycling.
                    self.final_point = get_point_relative(
                        self.cfg['scheduling']['final cycle point'],
                        self.initial_point
                    ).standardise()
            else:
                try:
                    # Relative, ISO8601 cycling.
                    self.final_point = get_point_relative(
                        final_point_string, self.initial_point).standardise()
                except ValueError:
                    # (not relative)
                    pass
            if self.final_point is None:
                # Must be absolute.
                self.final_point = get_point(final_point_string).standardise()
            self.cfg['scheduling']['final cycle point'] = str(self.final_point)

        if (self.final_point is not None and
                self.initial_point > self.final_point):
            raise SuiteConfigError(
                "The initial cycle point:" +
                str(self.initial_point) + " is after the final cycle point:" +
                str(self.final_point) + ".")

        # Validate final cycle point against any constraints
        if (self.final_point is not None and
                self.cfg['scheduling']['final cycle point constraints']):
            valid_fcp = False
            for entry in (
                    self.cfg['scheduling']['final cycle point constraints']):
                possible_pt = get_point_relative(
                    entry, self.final_point).standardise()
                if self.final_point == possible_pt:
                    valid_fcp = True
                    break
            if not valid_fcp:
                constraints_str = str(
                    self.cfg['scheduling']['final cycle point constraints'])
                raise SuiteConfigError(
                    "Final cycle point %s does not meet the constraints %s" % (
                        str(self.final_point), constraints_str))

        # Parse special task cycle point offsets, and replace family names.
        LOG.debug("Parsing [special tasks]")
        for s_type in self.cfg['scheduling']['special tasks']:
            result = copy(self.cfg['scheduling']['special tasks'][s_type])
            extn = ''
            for item in self.cfg['scheduling']['special tasks'][s_type]:
                name = item
                if s_type == 'external-trigger':
                    match = RE_EXT_TRIGGER.match(item)
                    if match is None:
                        raise SuiteConfigError(
                            "Illegal %s spec: %s" % (s_type, item)
                        )
                    name, ext_trigger_msg = match.groups()
                    extn = "(" + ext_trigger_msg + ")"

                elif s_type in ['clock-trigger', 'clock-expire']:
                    match = RE_CLOCK_OFFSET.match(item)
                    if match is None:
                        raise SuiteConfigError(
                            "Illegal %s spec: %s" % (s_type, item)
                        )
                    if (self.cfg['scheduling']['cycling mode'] !=
                            Calendar.MODE_GREGORIAN):
                        raise SuiteConfigError(
                            "%s tasks require "
                            "[scheduling]cycling mode=%s" % (
                                s_type, Calendar.MODE_GREGORIAN)
                        )
                    name, offset_string = match.groups()
                    if not offset_string:
                        offset_string = "PT0M"
                    if cylc.flags.verbose:
                        if offset_string.startswith("-"):
                            LOG.warning(
                                "%s offsets are normally positive: %s" % (
                                    s_type, item))
                    try:
                        offset_interval = (
                            get_interval(offset_string).standardise())
                    except IntervalParsingError:
                        raise SuiteConfigError(
                            "Illegal %s spec: %s" % (
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
                    '[visualization]collapsed families: '
                    '%s is not a first parent' % fam)

        if is_reload and collapsed:
            # on suite reload retain an existing state of collapse
            # (used by the "cylc graph" viewer)
            self.closed_families = collapsed
        elif is_reload:
            self.closed_families = []
        else:
            self.closed_families = self.collapsed_families_rc
        for cfam in self.closed_families:
            if cfam not in self.runtime['descendants']:
                self.closed_families.remove(cfam)
                if not is_reload and cylc.flags.verbose:
                    LOG.warning(
                        '[visualization][collapsed families]: ' +
                        'family ' + cfam + ' not defined')

        # check for run mode override at suite level
        if self.cfg['cylc']['force run mode']:
            self.run_mode = self.cfg['cylc']['force run mode']

        self.process_config_env()

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
                LOG.warning(err_msg)
            if self.strict:
                raise SuiteConfigError(
                    'strict validation fails naked dummy tasks')

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
                    LOG.error(
                        "External trigger '%s'\n  used in tasks %s and %s." % (
                            msg, name, seen[msg]))
                    raise SuiteConfigError(
                        "external triggers must be used only once.")

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
            LOG.debug("Checking [visualization] node attributes")
            # TODO - these should probably be done in non-verbose mode too.
            # 1. node groups should contain valid namespace names
            nspaces = list(self.cfg['runtime'])
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
                LOG.warning(err_msg)

            # 2. node attributes must refer to node groups or namespaces
            bad = []
            for na in self.cfg['visualization']['node attributes']:
                if na not in ngs and na not in nspaces:
                    bad.append(na)
            if bad:
                err_msg = "undefined node attribute targets"
                for na in bad:
                    err_msg += "\n+ " + str(na)
                LOG.warning(err_msg)

        # 3. node attributes must be lists of quoted "key=value" pairs.
        fail = False
        for node, attrs in (
                self.cfg['visualization']['node attributes'].items()):
            for attr in attrs:
                # Check form is 'name = attr'.
                if attr.count('=') != 1:
                    fail = True
                    LOG.error(
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
        # require reordering task_attr in lib/cylc/graphing.py
        # TODO: graphing.py is gone now! ).

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
                    LOG.warning(
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
        if vfcp is not None and self.final_point is not None:
            if vfcp > self.final_point:
                self.cfg['visualization']['final cycle point'] = str(
                    self.final_point)

        # Replace suite and task name in suite and task URLs.
        self.cfg['meta']['URL'] = self.cfg['meta']['URL'] % {
            'suite_name': self.suite}
        # back-compat $CYLC_SUITE_NAME:
        self.cfg['meta']['URL'] = RE_SUITE_NAME_VAR.sub(
            self.suite, self.cfg['meta']['URL'])
        for name, cfg in self.cfg['runtime'].items():
            cfg['meta']['URL'] = cfg['meta']['URL'] % {
                'suite_name': self.suite, 'task_name': name}
            # back-compat $CYLC_SUITE_NAME and $CYLC_TASK_NAME:
            cfg['meta']['URL'] = RE_SUITE_NAME_VAR.sub(
                self.suite, cfg['meta']['URL'])
            cfg['meta']['URL'] = RE_TASK_NAME_VAR.sub(
                name, cfg['meta']['URL'])

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
                    'circular edges detected:' + err_msg)

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
                replicate(newruntime[name], namespace_dict)
                if indices:
                    # Put parameter values in task environments.
                    self.task_param_vars[name] = indices
                    new_environ = OrderedDictWithDefaults()
                    if 'environment' in newruntime[name]:
                        new_environ = newruntime[name]['environment'].copy()
                    newruntime[name]['environment'] = new_environ
                if 'inherit' in newruntime[name]:
                    # Allow inheritance from parameterized namespaces.
                    parents = newruntime[name]['inherit']
                    origin = 'inherit = %s' % ', '.join(parents)
                    repl_parents = []
                    for parent in parents:
                        repl_parents.append(
                            name_expander.expand_parent_params(
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
        """Check for illegal environment variable names"""
        bad = {}
        for label, item in self.cfg['runtime'].items():
            for key in ('environment', 'parameter environment templates'):
                if key in item:
                    res = check_varnames(item[key])
                    if res:
                        bad[(label, key)] = res
        if bad:
            err_msg = "bad env variable names:"
            for (label, key), names in bad.items():
                err_msg += '\nNamespace:\t%s [%s]' % (label, key)
                for name in names:
                    err_msg += "\n\t\t%s" % name
            LOG.error(err_msg)
            raise SuiteConfigError(
                "Illegal environment variable name(s) detected")

    def check_param_env_tmpls(self):
        """Check for illegal parameter environment templates"""
        parameter_values = dict(
            (key, values[0])
            for key, values in self.parameters[0].items() if values)
        bads = set()
        for namespace, item in self.cfg['runtime'].items():
            if 'parameter environment templates' not in item:
                continue
            for name, tmpl in item['parameter environment templates'].items():
                try:
                    value = tmpl % parameter_values
                except KeyError:
                    bads.add((namespace, name, tmpl, 'bad parameter'))
                except TypeError:
                    bads.add((
                        namespace, name, tmpl,
                        'wrong data type for parameter'))
                except ValueError:
                    bads.add((namespace, name, tmpl, 'bad template syntax'))
                else:
                    if value == tmpl:  # Not a template
                        bads.add((namespace, name, tmpl, 'not a template'))
        if bads:
            LOG.error("bad parameter environment template:\n  %s" % (
                "\n  ".join('[%s]%s=%s  # %s' % bad for bad in sorted(bads))))
            raise SuiteConfigError(
                "Illegal parameter environment template(s) detected")

    def filter_env(self):
        """Filter environment variables after sparse inheritance"""
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
                        "undefined parent for " + name + ": " + p)
            if pts[0] == "None":
                if len(pts) < 2:
                    raise SuiteConfigError(
                        "null parentage for " + name)
                demoted[name] = pts[1]
                pts = pts[1:]
                first_parents[name] = ['root']
            else:
                first_parents[name] = [pts[0]]
            self.runtime['parents'][name] = pts

        if cylc.flags.verbose and demoted:
            log_msg = "First parent(s) demoted to secondary:"
            for n, p in demoted.items():
                log_msg += "\n + %s as parent of '%s'" % (p, n)
            LOG.debug(log_msg)

        c3 = C3(self.runtime['parents'])
        c3_single = C3(first_parents)

        for name in self.cfg['runtime']:
            try:
                self.runtime['linearized ancestors'][name] = c3.mro(name)
                self.runtime['first-parent ancestors'][name] = (
                    c3_single.mro(name))
            except RecursionError:
                raise SuiteConfigError(
                    "circular [runtime] inheritance?")
            except Exception as exc:
                # catch inheritance errors
                # TODO - specialise MRO exceptions
                raise SuiteConfigError(str(exc))

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
        LOG.debug("Parsing the runtime namespace hierarchy")

        results = OrderedDictWithDefaults()
        # n_reps = 0
        already_done = {}  # to store already computed namespaces by mro

        # Loop through runtime members, 'root' first.
        nses = list(self.cfg['runtime'])
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
                # variables) in deep hierarchies, but results may vary...
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
    #         LOG.info(log_msg)

    def compute_runahead_limits(self):
        """Extract the runahead limits information."""
        max_cycles = self.cfg['scheduling']['max active cycle points']
        if max_cycles == 0:
            raise SuiteConfigError(
                "max cycle points must be greater than %s" %
                (max_cycles)
            )
        self.max_num_active_cycle_points = self.cfg['scheduling'][
            'max active cycle points']

        limit = self.cfg['scheduling']['runahead limit']
        if not limit:
            limit = None
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

        LOG.debug("Configuring internal queues")

        # First add all tasks to the default queue.
        all_task_names = self.get_task_name_list()
        queues[self.Q_DEFAULT]['members'] = all_task_names

        # Then reassign to other queues as requested.
        warnings = []
        requeued = []
        for key, queue in list(queues.copy().items()):
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
                LOG.warning(err_msg)

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
            LOG.debug(log_msg)

    def configure_suite_state_polling_tasks(self):
        # Check custom script is not defined for automatic suite polling tasks.
        for l_task in self.suite_polling_tasks:
            try:
                cs = self.pcfg.get(sparse=True)['runtime'][l_task]['script']
            except KeyError:
                pass
            else:
                if cs:
                    # (allow explicit blanking of inherited script)
                    raise SuiteConfigError(
                        "script cannot be defined for automatic" +
                        " suite polling task '%s':\n%s" % (l_task, cs))
        # Generate the automatic scripting.
        for name, tdef in list(self.taskdefs.items()):
            if name not in self.suite_polling_tasks:
                continue
            rtc = tdef.rtconfig
            comstr = "cylc suite-state" + \
                     " --task=" + tdef.suite_polling_cfg['task'] + \
                     " --point=$CYLC_TASK_CYCLE_POINT"
            for key, fmt in [
                    ('user', ' --%s=%s'),
                    ('host', ' --%s=%s'),
                    ('interval', ' --%s=%d'),
                    ('max-polls', ' --%s=%s'),
                    ('run-dir', ' --%s=%s')]:
                if rtc['suite state polling'][key]:
                    comstr += fmt % (key, rtc['suite state polling'][key])
            if rtc['suite state polling']['message']:
                comstr += " --message='%s'" % (
                    rtc['suite state polling']['message'])
            else:
                comstr += " --status=" + tdef.suite_polling_cfg['status']
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
                    rtc['simulation']['time limit buffer'])).get_seconds()
            )
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
                    tree[key] = SuiteSrvFilesManager.NO_TITLE
            elif isinstance(val, dict):
                self.add_tree_titles(val)

    def get_namespace_list(self, which):
        names = []
        if which == 'graphed tasks':
            # tasks used only in the graph
            names = list(self.taskdefs)
        elif which == 'all namespaces':
            # all namespaces
            names = list(self.cfg['runtime'])
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
                result[ns] = SuiteSrvFilesManager.NO_TITLE

        return result

    def get_mro(self, ns):
        try:
            mro = self.runtime['linearized ancestors'][ns]
        except KeyError:
            mro = ["no such namespace: " + ns]
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

    def process_suite_env(self):
        """Suite context is exported to the local environment."""
        for var, val in [
                ('CYLC_SUITE_NAME', self.suite),
                ('CYLC_DEBUG', str(cylc.flags.debug).lower()),
                ('CYLC_VERBOSE', str(cylc.flags.verbose).lower()),
                ('CYLC_SUITE_DEF_PATH', self.fdir),
                ('CYLC_SUITE_RUN_DIR', self.run_dir),
                ('CYLC_SUITE_LOG_DIR', self.log_dir),
                ('CYLC_SUITE_WORK_DIR', self.work_dir),
                ('CYLC_SUITE_SHARE_DIR', self.share_dir)]:
            os.environ[var] = val

    def process_config_env(self):
        """Set local config derived environment."""
        os.environ['CYLC_UTC'] = str(get_utc_mode())
        os.environ['CYLC_SUITE_INITIAL_CYCLE_POINT'] = str(self.initial_point)
        os.environ['CYLC_SUITE_FINAL_CYCLE_POINT'] = str(self.final_point)
        os.environ['CYLC_CYCLING_MODE'] = self.cfg['scheduling'][
            'cycling mode']
        #     (global config auto expands environment variables in local paths)
        cenv = self.cfg['cylc']['environment'].copy()
        for var, val in cenv.items():
            cenv[var] = os.path.expandvars(val)
        #     path to suite bin directory for suite and event handlers
        cenv['PATH'] = os.pathsep.join([
            os.path.join(self.fdir, 'bin'), os.environ['PATH']])
        #     and to suite event handlers in this process.
        for var, val in cenv.items():
            os.environ[var] = val

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
            taskdef.check_for_explicit_cycling()
            # Check custom event handler templates compat with task meta
            if taskdef.rtconfig['events']:
                subs = dict((key, key) for key in self.TASK_EVENT_TMPL_KEYS)
                for key, value in self.cfg['meta'].items():
                    subs['suite_' + key.lower()] = value
                subs.update(taskdef.rtconfig['meta'])
                # Back compat.
                try:
                    subs['task_url'] = subs['URL']
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
                                    'bad task event handler template'
                                    ' %s: %s: %s' % (
                                        taskdef.name, value, repr(exc)))
        if cylc.flags.verbose:
            LOG.debug("Checking for defined tasks not used in the graph")
            for name in self.cfg['runtime']:
                if name not in self.taskdefs:
                    if name not in self.runtime['descendants']:
                        # Family triggers have been replaced with members.
                        LOG.warning(
                            'task "%s" not used in the graph.' % (name))
        # Check declared special tasks are valid.
        for task_type in self.cfg['scheduling']['special tasks']:
            for name in self.cfg['scheduling']['special tasks'][task_type]:
                if task_type in ['clock-trigger', 'clock-expire',
                                 'external-trigger']:
                    name = name.split('(', 1)[0]
                if not TaskID.is_valid_name(name):
                    raise SuiteConfigError(
                        'Illegal %s task name: %s' % (task_type, name))
                if (name not in self.taskdefs and
                        name not in self.cfg['runtime']):
                    msg = '%s task "%s" is not defined.' % (task_type, name)
                    if self.strict:
                        raise SuiteConfigError(msg)
                    else:
                        LOG.warning(msg)

    def get_task_name_list(self):
        # return a list of all tasks used in the dependency graph
        return list(self.taskdefs)

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
                    LOG.error("%s => %s" % (orig_lexpr, right))
                raise SuiteConfigError(
                    "self-edge detected: %s => %s" % (
                        left, right))
            self.edges[seq].add((left, right, suicide, conditional))

    def generate_taskdefs(self, orig_expr, left_nodes, right, seq):
        """Generate task definitions for all nodes in orig_expr."""

        for node in left_nodes + [right]:
            if not node or node.startswith('@'):
                # if right is None, lefts are lone nodes
                # for which we still define the taskdefs
                continue
            name, offset_is_from_icp, _, offset, _ = (
                GraphNodeParser.get_inst().parse(node))

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
                            'Message trigger offsets are obsolete.')

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
        xtrig_labels = set()
        for left in left_nodes:
            if left.startswith('@'):
                xtrig_labels.add(left[1:])
                continue
            # (GraphParseError checked above)
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
                        (str(-(last_point - first_point)), seq))
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

        if triggers:
            dependency = Dependency(expr_list, set(triggers.values()), suicide)
            self.taskdefs[right].add_dependency(dependency, seq)

        # Record xtrigger labels for each task name.
        if right not in self.xtriggers:
            self.xtriggers[right] = xtrig_labels
        else:
            self.xtriggers[right] = self.xtriggers[right].union(xtrig_labels)

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
                    if left.startswith('@'):
                        # @trigger node.
                        name = left
                        offset_is_from_icp = False
                        offset = None
                    else:
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
        graph_raw_edges.sort(key=lambda x: [y if y else '' for y in x])
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
        LOG.debug("Parsing the dependency graph")

        # Generate a map of *task* members of each family.
        # Note we could exclude 'root' from this and disallow use of 'root' in
        # the graph (which would probably be quite reasonable).
        family_map = {}
        for family, tasks in self.runtime['descendants'].items():
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
                raise SuiteConfigError("Initial cycle point referenced"
                                       " (^) but not defined.")
            if fcp:
                section = section.replace("$", fcp)
            elif "$" in section:
                raise SuiteConfigError("Final cycle point referenced"
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
                msg = 'Cannot process recurrence %s' % section
                msg += ' (initial cycle point=%s)' % icp
                msg += ' (final cycle point=%s)' % fcp
                if isinstance(exc, CylcError):
                    msg += ' %s' % exc.args[0]
                raise SuiteConfigError(msg)
            self.sequences.append(seq)
            parser = GraphParser(family_map, self.parameters)
            parser.parse_graph(graph)
            self.suite_polling_tasks.update(parser.suite_state_polling_tasks)
            self._proc_triggers(
                parser.triggers, parser.original, seq, task_triggers)

        xtcfg = self.cfg['scheduling']['xtriggers']
        # Taskdefs just know xtrigger labels.
        for task_name, xt_labels in self.xtriggers.items():
            for label in xt_labels:
                try:
                    xtrig = xtcfg[label]
                except KeyError:
                    if label == 'wall_clock':
                        # Allow predefined zero-offset wall clock xtrigger.
                        xtrig = SubFuncContext(
                            'wall_clock', 'wall_clock', [], {})
                    else:
                        raise SuiteConfigError(
                            "undefined xtrigger label: %s" % label)
                if xtrig.func_name.startswith('wall_clock'):
                    self.xtrigger_mgr.add_clock(label, xtrig)
                    # Replace existing xclock if the new offset is larger.
                    try:
                        offset = get_interval(xtrig.func_kwargs['offset'])
                    except KeyError:
                        offset = 0
                    old_label = self.taskdefs[task_name].xclock_label
                    if old_label is None:
                        self.taskdefs[task_name].xclock_label = label
                    else:
                        old_xtrig = self.xtrigger_mgr.clockx_map[old_label]
                        old_offset = get_interval(
                            old_xtrig.func_kwargs['offset'])
                        if offset > old_offset:
                            self.taskdefs[task_name].xclock_label = label
                else:
                    try:
                        if not callable(get_func(xtrig.func_name, self.fdir)):
                            raise SuiteConfigError(
                                f"xtrigger function not callable: "
                                f"{xtrig.func_name}")
                    except (ModuleNotFoundError, AttributeError):
                        raise SuiteConfigError(
                            f"xtrigger function not found: {xtrig.func_name}")
                    self.xtrigger_mgr.add_trig(label, xtrig)
                    self.taskdefs[task_name].xtrig_labels.add(label)

        # Detect use of xtrigger names with '@' prefix (creates a task).
        overlap = set(self.taskdefs.keys()).intersection(
            list(self.cfg['scheduling']['xtriggers']))
        if overlap:
            LOG.error(', '.join(overlap))
            raise SuiteConfigError('task and @xtrigger names clash')

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
                    LOG.error(orig_expr)
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
            taskd.param_var.update(self.task_param_vars[name])

        return taskd

    def describe(self, name):
        """Return title and description of the named task."""
        return self.taskdefs[name].describe()
