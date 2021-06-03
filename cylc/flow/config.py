# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
"""Parse and validate the workflow definition file

Set local values of variables to give workflow context before parsing
config, i.e for template filters (Jinja2, python ...etc) and possibly
needed locally by event handlers. This is needed for both running and
non-running workflow parsing (obtaining config/graph info). Potentially
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
from typing import (
    Any, Callable, Dict, List, Mapping, Optional, Set, TYPE_CHECKING, Tuple
)

from metomi.isodatetime.data import Calendar
from metomi.isodatetime.parsers import DurationParser
from metomi.isodatetime.exceptions import IsodatetimeError
from metomi.isodatetime.timezone import get_local_time_zone_format
from metomi.isodatetime.dumpers import TimePointDumper
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.util import replicate

from cylc.flow import LOG
from cylc.flow.c3mro import C3
from cylc.flow.listify import listify
from cylc.flow.exceptions import (
    CylcError, WorkflowConfigError, IntervalParsingError, TaskDefError,
    ParamExpandError)
from cylc.flow.graph_parser import GraphParser
from cylc.flow.param_expand import NameExpander
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.cfgspec.workflow import RawWorkflowConfig
from cylc.flow.cycling.loader import (
    get_point, get_point_relative, get_interval, get_interval_cls,
    get_sequence, get_sequence_cls, init_cyclers, get_dump_format,
    INTEGER_CYCLING_TYPE, ISO8601_CYCLING_TYPE)
from cylc.flow.cycling.integer import IntegerInterval
from cylc.flow.cycling.iso8601 import ingest_time, ISO8601Interval
import cylc.flow.flags
from cylc.flow.option_parsers import verbosity_to_env
from cylc.flow.graphnode import GraphNodeParser
from cylc.flow.pathutil import (
    get_workflow_run_dir,
    get_workflow_run_log_dir,
    get_workflow_run_share_dir,
    get_workflow_run_work_dir,
)
from cylc.flow.platforms import FORBIDDEN_WITH_PLATFORM
from cylc.flow.print_tree import print_tree
from cylc.flow.subprocctx import SubFuncContext
from cylc.flow.workflow_files import NO_TITLE
from cylc.flow.task_events_mgr import (
    EventData,
    get_event_handler_data
)
from cylc.flow.task_id import TaskID
from cylc.flow.task_outputs import TASK_OUTPUT_SUCCEEDED
from cylc.flow.task_trigger import TaskTrigger, Dependency
from cylc.flow.taskdef import TaskDef
from cylc.flow.unicode_rules import (
    TaskNameValidator,
    TaskOutputValidator,
    XtriggerNameValidator,
)
from cylc.flow.wallclock import (
    get_current_time_string, set_utc_mode, get_utc_mode)
from cylc.flow.xtrigger_mgr import XtriggerManager

if TYPE_CHECKING:
    from optparse import Values
    from cylc.flow.cycling import IntervalBase, PointBase, SequenceBase


RE_CLOCK_OFFSET = re.compile(r'(' + TaskID.NAME_RE + r')(?:\(\s*(.+)\s*\))?')
RE_EXT_TRIGGER = re.compile(r'(.*)\s*\(\s*(.+)\s*\)\s*')
RE_SEC_MULTI_SEQ = re.compile(r'(?![^(]+\)),')
RE_WORKFLOW_NAME_VAR = re.compile(r'\${?CYLC_WORKFLOW_(REG_)?NAME}?')
RE_TASK_NAME_VAR = re.compile(r'\${?CYLC_TASK_NAME}?')
RE_VARNAME = re.compile(r'^[a-zA-Z_][\w]*$')


def check_varnames(env):
    """Check a list of env var names for legality.

    Return a list of bad names (empty implies success).
    """
    bad = []
    for varname in env:
        if not RE_VARNAME.match(varname):
            bad.append(varname)
    return bad


def interpolate_template(tmpl, params_dict):
    """Try the string interpolation/formatting operator `%` on a template
    string with a dictionary of parameters.

    E.g. 'a_%(foo)d' % {'foo': 12}

    If it fails, raises ParamExpandError, but if the string does not contain
    `%(`, it just returns the string.
    """
    if '%(' not in tmpl:
        return tmpl  # User probably not trying to use param template
    try:
        return tmpl % params_dict
    except KeyError:
        raise ParamExpandError('bad parameter')
    except TypeError:
        raise ParamExpandError('wrong data type for parameter')
    except ValueError:
        raise ParamExpandError('bad template syntax')


# TODO: separate config for run and non-run purposes?


class WorkflowConfig:
    """Class for workflow configuration items and derived quantities."""

    CHECK_CIRCULAR_LIMIT = 100  # If no. tasks > this, don't check circular

    def __init__(
        self,
        workflow: str,
        fpath: str,
        options: Optional['Values'] = None,
        template_vars: Optional[Mapping[str, Any]] = None,
        is_reload: bool = False,
        output_fname: Optional[str] = None,
        xtrigger_mgr: Optional[XtriggerManager] = None,
        mem_log_func: Optional[Callable[[str], None]] = None,
        run_dir: Optional[str] = None,
        log_dir: Optional[str] = None,
        work_dir: Optional[str] = None,
        share_dir: Optional[str] = None
    ) -> None:

        self.mem_log = mem_log_func
        if self.mem_log is None:
            self.mem_log = lambda x: None
        self.mem_log("config.py:config.py: start init config")
        self.workflow = workflow  # workflow name
        self.fpath = fpath  # workflow definition
        self.fdir = os.path.dirname(fpath)
        self.run_dir = run_dir or get_workflow_run_dir(self.workflow)
        self.log_dir = log_dir or get_workflow_run_log_dir(self.workflow)
        self.share_dir = share_dir or get_workflow_run_share_dir(self.workflow)
        self.work_dir = work_dir or get_workflow_run_work_dir(self.workflow)
        self.options = options
        self.implicit_tasks: Set[str] = set()
        self.edges: Dict[
            'SequenceBase', Set[Tuple[str, str, bool, bool]]
        ] = {}
        self.taskdefs: Dict[str, TaskDef] = {}
        self.initial_point: Optional['PointBase'] = None
        self.start_point: Optional['PointBase'] = None
        self.final_point: Optional['PointBase'] = None
        self.first_graph = True
        self.clock_offsets = {}
        self.expiration_offsets = {}
        self.ext_triggers = {}  # Old external triggers (client/server)
        self.xtrigger_mgr = xtrigger_mgr
        self.workflow_polling_tasks = {}  # type: ignore # TODO figure out type
        self._last_graph_raw_id: Optional[tuple] = None
        self._last_graph_raw_edges = []  # type: ignore # TODO figure out type

        self.sequences: List['SequenceBase'] = []
        self.actual_first_point: Optional['PointBase'] = None
        self._start_point_for_actual_first_point: Optional['PointBase'] = None

        self.task_param_vars = {}  # type: ignore # TODO figure out type
        self.custom_runahead_limit: Optional['IntervalBase'] = None
        self.max_num_active_cycle_points = None

        # runtime hierarchy dicts keyed by namespace name:
        self.runtime: Dict[str, dict] = {  # TODO figure out type
            # lists of parent namespaces
            'parents': {},
            # lists of C3-linearized ancestor namespaces
            'linearized ancestors': {},
            # lists of first-parent ancestor namespaces
            'first-parent ancestors': {},
            # lists of all descendant namespaces
            # (not including the final tasks)
            'descendants': {},
            # lists of all descendant namespaces from the first-parent
            # hierarchy (first parents are collapsible in workflow
            # visualization)
            'first-parent descendants': {},
        }
        # tasks
        self.leaves = []  # TODO figure out type
        # one up from root
        self.feet = []  # type: ignore # TODO figure out type

        # Export local environmental workflow context before config parsing.
        self.process_workflow_env()

        # parse, upgrade, validate the workflow, but don't expand with default
        # items
        self.mem_log("config.py: before RawWorkflowConfig init")
        if output_fname:
            output_fname = os.path.expandvars(output_fname)
        self.pcfg = RawWorkflowConfig(
            fpath,
            output_fname,
            template_vars
        )
        self.mem_log("config.py: after RawWorkflowConfig init")
        self.mem_log("config.py: before get(sparse=True")
        self.cfg = self.pcfg.get(sparse=True)
        self.mem_log("config.py: after get(sparse=True)")

        if 'scheduler' in self.cfg and 'install' in self.cfg['scheduler']:
            self.get_validated_rsync_includes()

        # First check for the essential scheduling section.
        if 'scheduling' not in self.cfg:
            raise WorkflowConfigError("missing [scheduling] section.")
        if 'graph' not in self.cfg['scheduling']:
            raise WorkflowConfigError("missing [scheduling][[graph]] section.")
        # (The check that 'graph' is defined is below).

        # Override the workflow defn with an initial point from the CLI.
        icp_str = getattr(self.options, 'icp', None)
        if icp_str is not None:
            self.cfg['scheduling']['initial cycle point'] = icp_str

        self.prelim_process_graph()

        # allow test workflows with no [runtime]:
        if 'runtime' not in self.cfg:
            self.cfg['runtime'] = OrderedDictWithDefaults()

        if 'root' not in self.cfg['runtime']:
            self.cfg['runtime']['root'] = OrderedDictWithDefaults()

        try:
            # Ugly hack to avoid templates getting included in parameters
            parameter_values = {
                key: value for key, value in
                self.cfg['task parameters'].items()
                if key != 'templates'
            }
        except KeyError:
            # (Workflow config defaults not put in yet.)
            parameter_values = {}
        try:
            parameter_templates = self.cfg['task parameters']['templates']

        except KeyError:
            parameter_templates = {}

        # Check that parameter templates are a section
        if not hasattr(parameter_templates, 'update'):
            raise WorkflowConfigError(
                '[task parameters][templates] is a section. Don\'t use it '
                'as a parameter.'
            )

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

        # filter task environment variables after inheritance
        self.filter_env()

        # Now add config defaults. Items added prior to this end up in the
        # sparse dict (e.g. parameter-expanded namespaces).
        self.mem_log("config.py: before get(sparse=False)")
        self.cfg = self.pcfg.get(sparse=False)
        self.mem_log("config.py: after get(sparse=False)")

        # These 2 must be called before call to init_cyclers(self.cfg):
        self.process_utc_mode()
        self.process_cycle_point_tz()

        # after the call to init_cyclers, we can start getting proper points.
        init_cyclers(self.cfg)
        self.cycling_type = get_interval_cls().get_null().TYPE
        self.cycle_point_dump_format = get_dump_format(self.cycling_type)

        # Initial point from workflow definition (or CLI override above).
        self.process_initial_cycle_point()
        self.process_start_cycle_point()
        self.process_final_cycle_point()

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
                        raise WorkflowConfigError(
                            "Illegal %s spec: %s" % (s_type, item)
                        )
                    name, ext_trigger_msg = match.groups()
                    extn = "(" + ext_trigger_msg + ")"

                elif s_type in ['clock-trigger', 'clock-expire']:
                    match = RE_CLOCK_OFFSET.match(item)
                    if match is None:
                        raise WorkflowConfigError(
                            "Illegal %s spec: %s" % (s_type, item)
                        )
                    if (
                        self.cfg['scheduling']['cycling mode'] !=
                        Calendar.MODE_GREGORIAN
                    ):
                        raise WorkflowConfigError(
                            "%s tasks require "
                            "[scheduling]cycling mode=%s" % (
                                s_type, Calendar.MODE_GREGORIAN)
                        )
                    name, offset_string = match.groups()
                    if not offset_string:
                        offset_string = "PT0M"
                    if cylc.flow.flags.verbosity > 0:
                        if offset_string.startswith("-"):
                            LOG.warning(
                                "%s offsets are normally positive: %s" % (
                                    s_type, item))
                    try:
                        offset_interval = (
                            get_interval(offset_string).standardise())
                    except IntervalParsingError:
                        raise WorkflowConfigError(
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

        self.collapsed_families_config = (
            self.cfg['visualization']['collapsed families'])
        for fam in self.collapsed_families_config:
            if fam not in self.runtime['first-parent descendants']:
                raise WorkflowConfigError(
                    '[visualization]collapsed families: '
                    '%s is not a first parent' % fam)

        if getattr(options, 'collapsed', None):
            # (used by the "cylc graph" viewer)
            self.closed_families = getattr(self.options, 'collapsed', None)
        elif is_reload:
            self.closed_families = []
        else:
            self.closed_families = self.collapsed_families_config
        for cfam in self.closed_families:
            if cfam not in self.runtime['descendants']:
                self.closed_families.remove(cfam)
                if not is_reload and cylc.flow.flags.verbosity > 0:
                    LOG.warning(
                        '[visualization][collapsed families]: ' +
                        'family ' + cfam + ' not defined')

        self.process_config_env()

        self.mem_log("config.py: before load_graph()")
        self.load_graph()
        self.mem_log("config.py: after load_graph()")

        self.process_runahead_limit()

        if self.run_mode('simulation', 'dummy', 'dummy-local'):
            self.configure_sim_modes()

        self.configure_workflow_state_polling_tasks()

        self._check_task_event_handlers()
        self._check_special_tasks()  # adds to self.implicit_tasks
        self._check_explicit_cycling()

        self._check_implicit_tasks()
        self.validate_namespace_names()

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
                    raise WorkflowConfigError(
                        "external triggers must be used only once.")

        ngs = self.cfg['visualization']['node groups']
        # If a node group member is a family, include its descendants too.
        replace = {}  # type: ignore # TODO figure out type
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

        if cylc.flow.flags.verbosity > 0:
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
            bad_nas = []
            for na in self.cfg['visualization']['node attributes']:
                if na not in ngs and na not in nspaces:
                    bad_nas.append(na)
            if bad_nas:
                err_msg = "undefined node attribute targets"
                for na in bad_nas:
                    err_msg += f"\n+ {na}"
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
            raise WorkflowConfigError(
                "Node attributes must be of the form "
                "'key1=value1', 'key2=value2', etc."
            )

        # (Note that we're retaining 'default node attributes' even
        # though this could now be achieved by styling the root family,
        # because putting default attributes for root in the flow.cylc spec
        # results in root appearing last in the ordered dict of node
        # names, so it overrides the styling for lesser groups and
        # nodes, whereas the reverse is needed - fixing this would
        # require reordering task_attr in cylc/flow/graphing.py
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
        for key in ('initial', 'final'):
            vis_str = getattr(self.options, 'vis_' + key, None)
            if vis_str:
                self.cfg['visualization'][key + ' cycle point'] = vis_str

        # For static visualization, start point defaults to workflow initial
        # point; stop point must be explicit with initial point, or None.
        if self.cfg['visualization']['initial cycle point'] is None:
            self.cfg['visualization']['initial cycle point'] = (
                self.cfg['scheduling']['initial cycle point'])
            # If viz initial point is None don't accept a final point.
            if self.cfg['visualization']['final cycle point'] is not None:
                if cylc.flow.flags.verbosity > 0:
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
            except IsodatetimeError:
                vfcp = get_point(
                    self.cfg['visualization']['final cycle point']
                )
                if vfcp is not None:
                    vfcp = vfcp.standardise()
        else:
            vfcp = None

        # A viz final point can't be beyond the workflow final point.
        if vfcp is not None and self.final_point is not None:
            if vfcp > self.final_point:
                self.cfg['visualization']['final cycle point'] = str(
                    self.final_point)

        # Replace workflow and task name in workflow and task URLs.
        self.cfg['meta']['URL'] = self.cfg['meta']['URL'] % {
            'workflow_name': self.workflow}
        # BACK COMPAT: CYLC_WORKFLOW_NAME
        # from:
        #     Cylc7
        # to:
        #     Cylc8
        # remove at:
        #     Cylc9
        self.cfg['meta']['URL'] = RE_WORKFLOW_NAME_VAR.sub(
            self.workflow, self.cfg['meta']['URL'])
        for name, cfg in self.cfg['runtime'].items():
            cfg['meta']['URL'] = cfg['meta']['URL'] % {
                'workflow_name': self.workflow, 'task_name': name}
            # BACK COMPAT: CYLC_WORKFLOW_NAME, CYLC_TASK_NAME
            # from:
            #     Cylc7
            # to:
            #     Cylc8
            # remove at:
            #     Cylc9
            cfg['meta']['URL'] = RE_WORKFLOW_NAME_VAR.sub(
                self.workflow, cfg['meta']['URL'])
            cfg['meta']['URL'] = RE_TASK_NAME_VAR.sub(
                name, cfg['meta']['URL'])

        if getattr(self.options, 'is_validate', False):
            self.mem_log("config.py: before _check_circular()")
            self._check_circular()
            self.mem_log("config.py: after _check_circular()")

        self.mem_log("config.py: end init config")

    def prelim_process_graph(self) -> None:
        """Ensure graph is not empty; set integer cycling mode and icp/fcp = 1
        for simplest "R1 = foo" type graphs.
        """
        graphdict = self.cfg['scheduling']['graph']
        if not any(graphdict.values()):
            raise WorkflowConfigError('No workflow dependency graph defined.')

        if (
            'cycling mode' not in self.cfg['scheduling'] and
            self.cfg['scheduling'].get('initial cycle point', '1') == '1' and
            all(item in ['graph', '1', 'R1'] for item in graphdict)
        ):
            # Pure acyclic graph, assume integer cycling mode with '1' cycle
            self.cfg['scheduling']['cycling mode'] = INTEGER_CYCLING_TYPE
            for key in ('initial cycle point', 'final cycle point'):
                if key not in self.cfg['scheduling']:
                    self.cfg['scheduling'][key] = '1'

    def process_utc_mode(self):
        """Set UTC mode from config or from stored value on restart.

        Sets:
            self.cfg['scheduler']['UTC mode']
            The UTC mode flag
        """
        cfg_utc_mode = self.cfg['scheduler']['UTC mode']
        # Get the original UTC mode if restart:
        orig_utc_mode = getattr(self.options, 'utc_mode', None)
        if orig_utc_mode is None:
            # Not a restart - will save config value
            if cfg_utc_mode is not None:
                orig_utc_mode = cfg_utc_mode
            else:
                orig_utc_mode = glbl_cfg().get(['scheduler', 'UTC mode'])
        elif cfg_utc_mode is not None and cfg_utc_mode != orig_utc_mode:
            LOG.warning(
                "UTC mode = {0} specified in configuration, but is stored as "
                "{1} from the initial run. The workflow will continue to use "
                "UTC mode = {1}"
                .format(cfg_utc_mode, orig_utc_mode)
            )
        self.cfg['scheduler']['UTC mode'] = orig_utc_mode
        set_utc_mode(orig_utc_mode)

    def process_cycle_point_tz(self):
        """Set the cycle point time zone from config or from stored value
        on restart.

        Ensure workflows restart with the same cycle point time zone even after
        system time zone changes e.g. DST (the value is put in db by
        Scheduler).

        Sets:
            self.cfg['scheduler']['cycle point time zone']
        """
        cfg_cp_tz = self.cfg['scheduler'].get('cycle point time zone')
        # Get the original workflow run time zone if restart:
        orig_cp_tz = getattr(self.options, 'cycle_point_tz', None)
        if orig_cp_tz is None:
            # Not a restart
            if cfg_cp_tz is None:
                if get_utc_mode() is True:
                    orig_cp_tz = 'Z'
                else:
                    orig_cp_tz = get_local_time_zone_format()
            else:
                orig_cp_tz = cfg_cp_tz
        elif cfg_cp_tz is not None:
            dmp = TimePointDumper()
            if dmp.get_time_zone(cfg_cp_tz) != dmp.get_time_zone(orig_cp_tz):
                LOG.warning(
                    "cycle point time zone = {0} specified in configuration, "
                    "but there is a stored value of {1} from the initial run. "
                    "The workflow will continue to run in {1}"
                    .format(cfg_cp_tz, orig_cp_tz)
                )
        self.cfg['scheduler']['cycle point time zone'] = orig_cp_tz

    def process_initial_cycle_point(self):
        """Validate and set initial cycle point from flow.cylc or options.

        Sets:
            self.initial_point
            self.cfg['scheduling']['initial cycle point']
            self.options.icp
        Raises:
            WorkflowConfigError - if it fails to validate
        """
        orig_icp = self.cfg['scheduling']['initial cycle point']
        if self.cycling_type == INTEGER_CYCLING_TYPE:
            if orig_icp is None:
                orig_icp = '1'
            icp = orig_icp
        elif self.cycling_type == ISO8601_CYCLING_TYPE:
            if orig_icp is None:
                raise WorkflowConfigError(
                    "This workflow requires an initial cycle point.")
            if orig_icp == "now":
                icp = get_current_time_string()
            else:
                try:
                    icp = ingest_time(orig_icp, get_current_time_string())
                except IsodatetimeError as exc:
                    raise WorkflowConfigError(str(exc))
        if orig_icp != icp:
            # now/next()/prev() was used, need to store evaluated point in DB
            self.options.icp = icp
        self.initial_point = get_point(icp).standardise()
        self.cfg['scheduling']['initial cycle point'] = str(self.initial_point)

        # Validate initial cycle point against any constraints
        constraints = self.cfg['scheduling']['initial cycle point constraints']
        if constraints:
            valid_icp = False
            for entry in constraints:
                possible_pt = get_point_relative(
                    entry, self.initial_point
                ).standardise()
                if self.initial_point == possible_pt:
                    valid_icp = True
                    break
            if not valid_icp:
                raise WorkflowConfigError(
                    f"Initial cycle point {self.initial_point} does not meet "
                    f"the constraints {constraints}")

    def process_start_cycle_point(self):
        """Set the start cycle point from options.

        Sets:
            self.options.startcp
            self.start_point
        """
        if getattr(self.options, 'startcp', None) is not None:
            # Warm start from a point later than initial point.
            if self.options.startcp == 'now':
                self.options.startcp = get_current_time_string()
            self.start_point = get_point(self.options.startcp).standardise()
        else:
            # Cold start.
            self.start_point = self.initial_point

    def process_final_cycle_point(self):
        """Validate and set the final cycle point from flow.cylc or options.

        Sets:
            self.final_point
            self.cfg['scheduling']['final cycle point']
        Raises:
            WorkflowConfigError - if it fails to validate
        """
        if (
            self.cfg['scheduling']['final cycle point'] is not None and
            not self.cfg['scheduling']['final cycle point'].strip()
        ):
            self.cfg['scheduling']['final cycle point'] = None
        fcp_str = getattr(self.options, 'fcp', None)
        if fcp_str == 'ignore':
            fcp_str = self.options.fcp = None
        if fcp_str is None:
            fcp_str = self.cfg['scheduling']['final cycle point']
        if fcp_str is not None:
            # Is the final "point"(/interval) relative to initial?
            if self.cycling_type == INTEGER_CYCLING_TYPE:
                if "P" in fcp_str:
                    # Relative, integer cycling.
                    self.final_point = get_point_relative(
                        self.cfg['scheduling']['final cycle point'],
                        self.initial_point
                    ).standardise()
            else:
                try:
                    # Relative, ISO8601 cycling.
                    self.final_point = get_point_relative(
                        fcp_str, self.initial_point).standardise()
                except IsodatetimeError:
                    # (not relative)
                    pass
            if self.final_point is None:
                # Must be absolute.
                self.final_point = get_point(fcp_str).standardise()
            self.cfg['scheduling']['final cycle point'] = str(self.final_point)

        if (self.final_point is not None and
                self.initial_point > self.final_point):
            raise WorkflowConfigError(
                f"The initial cycle point:{self.initial_point} is after the "
                f"final cycle point:{self.final_point}.")

        # Validate final cycle point against any constraints
        constraints = self.cfg['scheduling']['final cycle point constraints']
        if constraints and self.final_point is not None:
            valid_fcp = False
            for entry in constraints:
                possible_pt = get_point_relative(
                    entry, self.final_point).standardise()
                if self.final_point == possible_pt:
                    valid_fcp = True
                    break
            if not valid_fcp:
                raise WorkflowConfigError(
                    f"Final cycle point {self.final_point} does not "
                    f"meet the constraints {constraints}")

    def _check_implicit_tasks(self) -> None:
        """Raise WorkflowConfigError if implicit tasks are found in graph or
        queue config, unless allowed by config."""
        if self.implicit_tasks:
            print_limit = 10
            implicit_tasks_str = '\n    * '.join(
                list(self.implicit_tasks)[:print_limit])
            num = len(self.implicit_tasks)
            if num > print_limit:
                implicit_tasks_str = (
                    f"{implicit_tasks_str}\n    and {num} more")
            err_msg = (
                "implicit tasks detected (no entry under [runtime]):\n"
                f"    * {implicit_tasks_str}")
            if self.cfg['scheduler']['allow implicit tasks']:
                LOG.debug(err_msg)
            else:
                raise WorkflowConfigError(
                    f"{err_msg}\n\n"
                    "To allow implicit tasks, use "
                    "'flow.cylc[scheduler]allow implicit tasks'")

    def _check_circular(self):
        """Check for circular dependence in graph."""
        if (len(self.taskdefs) > self.CHECK_CIRCULAR_LIMIT and
                not getattr(self.options, 'check_circular', False)):
            LOG.warning(
                f"Number of tasks is > {self.CHECK_CIRCULAR_LIMIT}; will not "
                "check graph for circular dependencies. To enforce this "
                "check, use the option --check-circular.")
            return
        start_point_string = self.cfg['visualization']['initial cycle point']
        raw_graph = self.get_graph_raw(start_point_string,
                                       stop_point_string=None)
        lhs2rhss = {}  # left hand side to right hand sides
        rhs2lhss = {}  # right hand side to left hand sides
        for lhs, rhs in raw_graph:
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
                raise WorkflowConfigError(
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
        sxs = {x01 for x01 in x2ys if x01 not in y2xs}
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

        TODO - this will have an impact on memory footprint for large workflows
        with a lot of runtime config. We should consider ditching OrderedDict
        and instead using an ordinary dict

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

    def validate_namespace_names(self):
        """Validate task and family names."""
        for name in self.cfg['runtime']:
            success, message = TaskNameValidator.validate(name)
            if not success:
                raise WorkflowConfigError(
                    f'task/family name {message}\n[runtime][[{name}]]'
                )

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
            raise WorkflowConfigError(
                "Illegal environment variable name(s) detected")

    def check_param_env_tmpls(self):
        """Check for illegal parameter environment templates"""
        parameter_values = {
            key: values[0]
            for key, values in self.parameters[0].items() if values
        }
        bads = set()
        for task_name, task_items in self.cfg['runtime'].items():
            if 'environment' not in task_items:
                continue
            for name, tmpl in task_items['environment'].items():
                try:
                    interpolate_template(tmpl, parameter_values)
                except ParamExpandError as descr:
                    bads.add((task_name, name, tmpl, descr))
        if bads:
            LOG.warning(
                'bad parameter environment template:\n    '
                '\n    '.join(
                    '[runtime][%s][environment]%s = %s  # %s' %
                    bad for bad in sorted(bads)
                )
            )

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
                    raise WorkflowConfigError(
                        "undefined parent for " + name + ": " + p)
            if pts[0] == "None":
                if len(pts) < 2:
                    raise WorkflowConfigError(
                        "null parentage for " + name)
                demoted[name] = pts[1]
                pts = pts[1:]
                first_parents[name] = ['root']
            else:
                first_parents[name] = [pts[0]]
            self.runtime['parents'][name] = pts

        if cylc.flow.flags.verbosity > 0 and demoted:
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
                raise WorkflowConfigError(
                    "circular [runtime] inheritance?")
            except Exception as exc:
                # catch inheritance errors
                # TODO - specialise MRO exceptions
                raise WorkflowConfigError(str(exc))

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

    def compute_inheritance(self):
        LOG.debug("Parsing the runtime namespace hierarchy")

        # TODO: Note an unused alternative mechanism was removed here
        # (March 2020). It stored the result of each completed MRO and
        # re-used these wherever possible. This could be more efficient
        # for full namespaces in deep hierarchies. We should go back and
        # look if inheritance computation becomes a problem.

        results = OrderedDictWithDefaults()

        # Loop through runtime members, 'root' first.
        nses = list(self.cfg['runtime'])
        nses.sort(key=lambda ns: ns != 'root')
        for ns in nses:
            # for each namespace ...

            hierarchy = copy(self.runtime['linearized ancestors'][ns])
            hierarchy.reverse()

            result = OrderedDictWithDefaults()

            # Go up the linearized MRO from root, replicating or
            # overriding each namespace element as we go.
            for name in hierarchy:
                replicate(result, self.cfg['runtime'][name])
                # n_reps += 1

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

    def process_runahead_limit(self):
        """Extract the runahead limits information."""
        limit = self.cfg['scheduling']['runahead limit']
        if limit.isdigit():
            limit = f'PT{limit}H'
            LOG.warning(
                'Use of a raw number of hours for the runahead limit is '
                f'deprecated. Use "{limit}" instead')

        number_limit_regex = re.compile(r'^P\d+$')
        time_limit_regexes = DurationParser.DURATION_REGEXES

        if number_limit_regex.fullmatch(limit):
            self.custom_runahead_limit = IntegerInterval(limit)
            # Handle "runahead limit = P0":
            if self.custom_runahead_limit.is_null():
                self.custom_runahead_limit = IntegerInterval('P1')
        elif (self.cycling_type == ISO8601_CYCLING_TYPE and
              any(tlr.fullmatch(limit) for tlr in time_limit_regexes)):
            self.custom_runahead_limit = ISO8601Interval(limit)
        else:
            raise WorkflowConfigError(
                f'bad runahead limit "{limit}" for {self.cycling_type} '
                'cycling type')

    def get_custom_runahead_limit(self):
        """Return the custom runahead limit (may be None)."""
        return self.custom_runahead_limit

    def get_max_num_active_cycle_points(self):
        """Return the maximum allowed number of pool cycle points."""
        return self.max_num_active_cycle_points

    def get_config(self, args, sparse=False):
        return self.pcfg.get(args, sparse)

    def adopt_orphans(self, orphans):
        # Called by the scheduler after reloading the workflow definition
        # at run time and finding any live task proxies whose
        # definitions have been removed from the workflow. Keep them
        # in the default queue and under the root family, until they
        # run their course and disappear.
        for orphan in orphans:
            self.runtime['linearized ancestors'][orphan] = [orphan, 'root']

    def configure_workflow_state_polling_tasks(self):
        # Check custom script not defined for automatic workflow polling tasks.
        for l_task in self.workflow_polling_tasks:
            try:
                cs = self.pcfg.get(sparse=True)['runtime'][l_task]['script']
            except KeyError:
                pass
            else:
                if cs:
                    # (allow explicit blanking of inherited script)
                    raise WorkflowConfigError(
                        "script cannot be defined for automatic" +
                        " workflow polling task '%s':\n%s" % (l_task, cs))
        # Generate the automatic scripting.
        for name, tdef in list(self.taskdefs.items()):
            if name not in self.workflow_polling_tasks:
                continue
            rtc = tdef.rtconfig
            comstr = (
                "cylc workflow-state"
                + " --task=" + tdef.workflow_polling_cfg['task']
                + " --point=$CYLC_TASK_CYCLE_POINT"
            )
            for key, fmt in [
                    ('user', ' --%s=%s'),
                    ('host', ' --%s=%s'),
                    ('interval', ' --%s=%d'),
                    ('max-polls', ' --%s=%s'),
                    ('run-dir', ' --%s=%s')]:
                if rtc['workflow state polling'][key]:
                    comstr += fmt % (key, rtc['workflow state polling'][key])
            if rtc['workflow state polling']['message']:
                comstr += " --message='%s'" % (
                    rtc['workflow state polling']['message'])
            else:
                comstr += " --status=" + tdef.workflow_polling_cfg['status']
            comstr += " " + tdef.workflow_polling_cfg['workflow']
            script = "echo " + comstr + "\n" + comstr
            rtc['script'] = script

    def configure_sim_modes(self):
        """Adjust task defs for simulation mode and dummy modes."""
        for tdef in self.taskdefs.values():
            # Compute simulated run time by scaling the execution limit.
            rtc = tdef.rtconfig
            limit = rtc['execution time limit']
            speedup = rtc['simulation']['speedup factor']
            if limit and speedup:
                sleep_sec = (DurationParser().parse(
                    str(limit)).get_seconds() / speedup)
            else:
                sleep_sec = DurationParser().parse(
                    str(rtc['simulation']['default run length'])
                ).get_seconds()
            rtc['execution time limit'] = (
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

            # All dummy modes should run on platform localhost
            # All Cylc 7 config items which conflict with platform are removed.
            for section, key, _ in FORBIDDEN_WITH_PLATFORM:
                if (section in rtc and key in rtc[section]):
                    rtc[section][key] = None
            rtc['platform'] = 'localhost'

            # Disable environment, in case it depends on env-script.
            rtc['environment'] = {}

            if tdef.run_mode == 'dummy-local':
                # Run all dummy tasks on the workflow host.
                rtc['platform'] = 'localhost'

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
                    tree[key] = NO_TITLE
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
                result[ns] = NO_TITLE

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

    def process_workflow_env(self):
        """Workflow context is exported to the local environment."""
        for key, value in {
            **verbosity_to_env(cylc.flow.flags.verbosity),
            'CYLC_WORKFLOW_NAME': self.workflow,
            'CYLC_WORKFLOW_RUN_DIR': self.run_dir,
            'CYLC_WORKFLOW_LOG_DIR': self.log_dir,
            'CYLC_WORKFLOW_WORK_DIR': self.work_dir,
            'CYLC_WORKFLOW_SHARE_DIR': self.share_dir,
            # BACK COMPAT: CYLC_WORKFLOW_DEF_PATH
            #   from: Cylc7
            'CYLC_WORKFLOW_DEF_PATH': self.run_dir,
        }.items():
            os.environ[key] = value

    def process_config_env(self):
        """Set local config derived environment."""
        os.environ['CYLC_UTC'] = str(get_utc_mode())
        os.environ['CYLC_WORKFLOW_INITIAL_CYCLE_POINT'] = str(
            self.initial_point
        )
        os.environ['CYLC_WORKFLOW_FINAL_CYCLE_POINT'] = str(self.final_point)
        os.environ['CYLC_CYCLING_MODE'] = self.cfg['scheduling'][
            'cycling mode']
        # Add workflow bin directory to PATH for workflow and event handlers
        os.environ['PATH'] = os.pathsep.join([
            os.path.join(self.fdir, 'bin'), os.environ['PATH']])

    def run_mode(self, *reqmodes):
        """Return the run mode.

        Combine command line option with configuration setting.
        If "reqmodes" is specified, return the boolean (mode in reqmodes).
        Otherwise, return the mode as a str.
        """
        mode = getattr(self.options, 'run_mode', None)
        if not mode:
            mode = 'live'
        if reqmodes:
            return mode in reqmodes
        else:
            return mode

    def _check_task_event_handlers(self):
        """Check custom event handler templates can be expanded.

        Ensures that any %(template_variables)s in task event handlers
        are present in the data that will be passed to them when called
        (otherwise they will fail).
        """
        for taskdef in self.taskdefs.values():
            if taskdef.rtconfig['events']:
                handler_data = {
                    item.value: ''
                    for item in EventData
                }
                handler_data.update(
                    get_event_handler_data(taskdef.rtconfig, self.cfg)
                )
                for key, values in taskdef.rtconfig['events'].items():
                    if values and (
                            key == 'handlers' or key.endswith(' handler')):
                        for handler_template in values:
                            try:
                                handler_template % handler_data
                            except (KeyError, ValueError) as exc:
                                raise WorkflowConfigError(
                                    f'bad task event handler template'
                                    f' {taskdef.name}:'
                                    f' {handler_template}:'
                                    f' {repr(exc)}'
                                )

    def _check_special_tasks(self):
        """Check declared special tasks are valid, and detect special
        implicit tasks"""
        for task_type in self.cfg['scheduling']['special tasks']:
            for name in self.cfg['scheduling']['special tasks'][task_type]:
                if task_type in ['clock-trigger', 'clock-expire',
                                 'external-trigger']:
                    name = name.split('(', 1)[0]
                if not TaskID.is_valid_name(name):
                    raise WorkflowConfigError(
                        f'Illegal {task_type} task name: {name}')
                if (name not in self.taskdefs and
                        name not in self.cfg['runtime']):
                    self.implicit_tasks.add(name)

    def _check_explicit_cycling(self):
        """Check that inter-cycle offsets refer to cycling tasks.

        E.G. foo[-P1] => bar requires foo to be defined in the
        graph somewhere.
        """
        for taskdef in self.taskdefs.values():
            taskdef.check_for_explicit_cycling()

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
                    LOG.error(f"{orig_lexpr} => {right}")
                raise WorkflowConfigError(
                    f"self-edge detected: {left} => {right}")
            self.edges[seq].add((left, right, suicide, conditional))

    def generate_taskdefs(self, orig_expr, left_nodes, right, seq, suicide):
        """Generate task definitions for all nodes in orig_expr."""

        for node in left_nodes + [right]:
            if not node or node.startswith('@'):
                # if right is None, lefts are lone nodes
                # for which we still define the taskdefs
                continue
            name, offset, _, offset_is_from_icp, _, _ = (
                GraphNodeParser.get_inst().parse(node))

            if name not in self.cfg['runtime']:
                # implicit inheritance from root
                self.implicit_tasks.add(name)
                # These can't just be a reference to root runtime as we have to
                # make some items task-specific: e.g. subst task name in URLs.
                self.cfg['runtime'][name] = OrderedDictWithDefaults()
                replicate(self.cfg['runtime'][name],
                          self.cfg['runtime']['root'])
                if 'root' not in self.runtime['descendants']:
                    # (happens when no runtimes are defined in flow.cylc)
                    self.runtime['descendants']['root'] = []
                if 'root' not in self.runtime['first-parent descendants']:
                    # (happens when no runtimes are defined in flow.cylc)
                    self.runtime['first-parent descendants']['root'] = []
                self.runtime['parents'][name] = ['root']
                self.runtime['linearized ancestors'][name] = [name, 'root']
                self.runtime['first-parent ancestors'][name] = [name, 'root']
                self.runtime['descendants']['root'].append(name)
                self.runtime['first-parent descendants']['root'].append(name)
                self.ns_defn_order.append(name)

            # check task name legality and create the taskdef
            taskdef = self.get_taskdef(name, orig_expr)

            if name in self.workflow_polling_tasks:
                taskdef.workflow_polling_cfg = {
                    'workflow': self.workflow_polling_tasks[name][0],
                    'task': self.workflow_polling_tasks[name][1],
                    'status': self.workflow_polling_tasks[name][2]}

            # Only add sequence to taskdef if explicit (not an offset).
            if offset:
                taskdef.used_in_offset_trigger = True
            elif suicide and name == right:
                # "foo => !bar" should not create taskdef bar
                pass
            else:
                taskdef.add_sequence(seq)

            # Record custom message outputs.
            for item in self.cfg['runtime'][name]['outputs'].items():
                output, task_message = item
                valid, msg = TaskOutputValidator.validate(task_message)
                if not valid:
                    raise WorkflowConfigError(
                        f'Invalid message trigger "[runtime][{name}][outputs]'
                        f'{output} = {task_message}" - {msg}'
                    )
                taskdef.outputs.add(item)

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
            expr_list = listify(lexpression)
        except SyntaxError:
            raise WorkflowConfigError('Error in expression "%s"' % lexpression)

        triggers = {}
        xtrig_labels = set()
        for left in left_nodes:
            if left.startswith('@'):
                xtrig_labels.add(left[1:])
                continue
            # (GraphParseError checked above)
            (name, offset, output, offset_is_from_icp,
             offset_is_irregular, offset_is_absolute) = (
                GraphNodeParser.get_inst().parse(left))

            # Qualifier.
            outputs = self.cfg['runtime'][name]['outputs']
            if outputs and (output in outputs):
                # Qualifier is a task message.
                qualifier = outputs[output]
            elif output:
                # Qualifier specified => standardise.
                qualifier = TaskTrigger.get_trigger_name(output)
            else:
                # No qualifier specified => use "succeeded".
                qualifier = TASK_OUTPUT_SUCCEEDED

            # Generate TaskTrigger if not already done.
            key = (name, offset, qualifier,
                   offset_is_irregular, offset_is_absolute,
                   offset_is_from_icp, self.initial_point)
            try:
                task_trigger = task_triggers[key]
            except KeyError:
                task_trigger = TaskTrigger(*key)
                task_triggers[key] = task_trigger

            triggers[left] = task_trigger

            # (name is left name)
            self.taskdefs[name].add_graph_child(task_trigger, right, seq)
            # graph_parents not currently used but might be needed soon:
            self.taskdefs[right].add_graph_parent(task_trigger, name, seq)

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

        validator = XtriggerNameValidator.validate
        for label in self.cfg['scheduling']['xtriggers']:
            valid, msg = validator(label)
            if not valid:
                raise WorkflowConfigError(
                    f'Invalid xtrigger name "{label}" - {msg}'
                )

        for label in xtrig_labels:
            try:
                xtrig = self.cfg['scheduling']['xtriggers'][label]
            except KeyError:
                if label == 'wall_clock':
                    # Allow "@wall_clock" in the graph as an undeclared
                    # zero-offset clock xtrigger.
                    xtrig = SubFuncContext(
                        'wall_clock', 'wall_clock', [], {})
                else:
                    raise WorkflowConfigError(f"xtrigger not defined: {label}")
            if (xtrig.func_name == 'wall_clock' and
                    self.cfg['scheduling']['cycling mode'] == (
                        INTEGER_CYCLING_TYPE)):
                sig = xtrig.get_signature()
                raise WorkflowConfigError(
                    f"clock xtriggers need date-time cycling: {label} = {sig}")
            if self.xtrigger_mgr is None:
                XtriggerManager.validate_xtrigger(label, xtrig, self.fdir)
            else:
                self.xtrigger_mgr.add_trig(label, xtrig, self.fdir)
            self.taskdefs[right].add_xtrig_label(label, seq)

    def get_actual_first_point(self, start_point):
        """Get actual first cycle point for the workflow

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
                      ungroup_all=False):
        """Convert the abstract graph edges (self.edges, etc) to actual edges

        Actual edges have concrete ranges of cycle points.

        In validate mode, set ungroup_all to True, and only return non-suicide
        edges with left and right nodes.
        """
        is_validate = getattr(
            self.options, 'is_validate', False)  # this is for _check_circular
        if is_validate:
            ungroup_all = True
        if group_nodes is None:
            group_nodes = []
        if ungroup_nodes is None:
            ungroup_nodes = []

        if self.first_graph:
            self.first_graph = False
            if not self.collapsed_families_config and not ungroup_all:
                # initially default to collapsing all families if
                # "[visualization]collapsed families" not defined
                group_all = True

        first_parent_descendants = self.runtime['first-parent descendants']
        if group_all:
            # Group all family nodes
            if self.collapsed_families_config:
                self.closed_families = copy(self.collapsed_families_config)
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

        workflow_final_point = get_point(
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
                if (workflow_final_point is not None
                        and point > workflow_final_point):
                    # Beyond workflow final cycle point.
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
                        name, offset, _, offset_is_from_icp, _, _ = (
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
        graph_raw_edges.sort(key=lambda x: [y if y else '' for y in x[:2]])
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
                except IsodatetimeError:
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

        graphdict = self.cfg['scheduling']['graph']
        if 'graph' in graphdict:
            section = get_sequence_cls().get_async_expr()
            graphdict[section] = graphdict.pop('graph')

        icp = self.cfg['scheduling']['initial cycle point']
        fcp = self.cfg['scheduling']['final cycle point']

        # Make a stack of sections and graphs [(sec1, graph1), ...]
        sections = []
        for section, value in self.cfg['scheduling']['graph'].items():
            # Substitute initial and final cycle points.
            if icp:
                section = section.replace("^", icp)
            elif "^" in section:
                raise WorkflowConfigError("Initial cycle point referenced"
                                          " (^) but not defined.")
            if fcp:
                section = section.replace("$", fcp)
            elif "$" in section:
                raise WorkflowConfigError("Final cycle point referenced"
                                          " ($) but not defined.")
            # If the section consists of more than one sequence, split it up.
            new_sections = RE_SEC_MULTI_SEQ.split(section)
            if len(new_sections) > 1:
                for new_section in new_sections:
                    sections.append((new_section.strip(), value))
            else:
                sections.append((section, value))

        # Parse and process each graph section.
        task_triggers = {}
        for section, graph in sections:
            try:
                seq = get_sequence(section, icp, fcp)
            except (AttributeError, TypeError, ValueError, CylcError) as exc:
                if cylc.flow.flags.verbosity > 1:
                    traceback.print_exc()
                msg = 'Cannot process recurrence %s' % section
                msg += ' (initial cycle point=%s)' % icp
                msg += ' (final cycle point=%s)' % fcp
                if isinstance(exc, CylcError):
                    msg += ' %s' % exc.args[0]
                raise WorkflowConfigError(msg)
            self.sequences.append(seq)
            parser = GraphParser(family_map, self.parameters)
            parser.parse_graph(graph)
            self.workflow_polling_tasks.update(
                parser.workflow_state_polling_tasks)
            self._proc_triggers(
                parser.triggers, parser.original, seq, task_triggers)

        # Detect use of xtrigger names with '@' prefix (creates a task).
        overlap = set(self.taskdefs.keys()).intersection(
            list(self.cfg['scheduling']['xtriggers']))
        if overlap:
            LOG.error(', '.join(overlap))
            raise WorkflowConfigError('task and @xtrigger names clash')

    def _proc_triggers(self, triggers, original, seq, task_triggers):
        """Define graph edges, taskdefs, and triggers, from graph sections."""
        for right, val in triggers.items():
            for expr, trigs in val.items():
                lefts, suicide = trigs
                orig = original[right][expr]
                self.generate_edges(expr, orig, lefts, right, seq, suicide)
                self.generate_taskdefs(orig, lefts, right, seq, suicide)
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

    def get_taskdef(
        self, name: str, orig_expr: Optional[str] = None
    ) -> TaskDef:
        """Return an instance of TaskDef for task name."""
        if name not in self.taskdefs:
            try:
                self.taskdefs[name] = self._get_taskdef(name)
            except TaskDefError as exc:
                if orig_expr:
                    LOG.error(orig_expr)
                raise WorkflowConfigError(str(exc))
        return self.taskdefs[name]

    def _get_taskdef(self, name: str) -> TaskDef:
        """Get the dense task runtime."""
        # (TaskDefError caught above)

        try:
            rtcfg = self.cfg['runtime'][name]
        except KeyError:
            raise WorkflowConfigError("Task not defined: %s" % name)
        # We may want to put in some handling for cases of changing the
        # initial cycle via restart (accidentally or otherwise).

        # Get the taskdef object for generating the task proxy class
        taskd = TaskDef(
            name, rtcfg, self.run_mode(), self.start_point,
            self.initial_point)

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

    def get_ref_log_name(self):
        """Return path to reference log (for reference test)."""
        return os.path.join(self.fdir, 'reference.log')

    def get_expected_failed_tasks(self):
        """Return list of expected failed tasks.

        Return:
        - An empty list if NO task is expected to fail.
        - A list of NAME.CYCLE for the tasks that are expected to fail
          in reference test mode.
        - None if there is no expectation either way.
        """
        if self.options.reftest:
            return self.cfg['scheduler']['events']['expected task failures']
        elif self.options.abort_if_any_task_fails:
            return []
        else:
            return None

    def get_validated_rsync_includes(self):
        """Validate and return items to be included in the file installation"""
        includes = self.cfg['scheduler']['install']
        illegal_includes = []
        for include in includes:
            if include.count("/") > 1:
                illegal_includes.append(f"{include}")
        if len(illegal_includes) > 0:
            raise WorkflowConfigError(
                "Error in [scheduler] install. "
                "Directories can only be from the top level, please "
                "reconfigure:" + str(illegal_includes)[1:-1])
        return includes
