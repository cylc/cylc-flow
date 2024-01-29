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

from contextlib import suppress
from copy import copy
from fnmatch import fnmatchcase
import os
from pathlib import Path
import re
from textwrap import wrap
import traceback
from typing import (
    Any, Callable, Dict, List, Mapping, Optional, Set, TYPE_CHECKING, Tuple,
    Union, Iterable
)

from metomi.isodatetime.data import Calendar
from metomi.isodatetime.parsers import DurationParser
from metomi.isodatetime.exceptions import IsodatetimeError
from metomi.isodatetime.timezone import get_local_time_zone_format
from metomi.isodatetime.dumpers import TimePointDumper

from cylc.flow import LOG
from cylc.flow.c3mro import C3
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.cfgspec.workflow import RawWorkflowConfig
from cylc.flow.cycling.loader import (
    get_point, get_point_relative, get_interval, get_interval_cls,
    get_sequence, get_sequence_cls, init_cyclers, get_dump_format,
    INTEGER_CYCLING_TYPE, ISO8601_CYCLING_TYPE
)
from cylc.flow.id import Tokens
from cylc.flow.cycling.integer import IntegerInterval
from cylc.flow.cycling.iso8601 import ingest_time, ISO8601Interval

from cylc.flow.exceptions import (
    CylcError,
    InputError,
    IntervalParsingError,
    ParamExpandError,
    TaskDefError,
    WorkflowConfigError,
)
import cylc.flow.flags
from cylc.flow.graph_parser import GraphParser
from cylc.flow.listify import listify
from cylc.flow.log_level import verbosity_to_env
from cylc.flow.graphnode import GraphNodeParser
from cylc.flow.param_expand import NameExpander
from cylc.flow.parsec.exceptions import ItemNotFoundError
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.util import replicate
from cylc.flow.pathutil import (
    get_workflow_name_from_id,
    get_cylc_run_dir,
    is_relative_to,
)
from cylc.flow.print_tree import print_tree
from cylc.flow.simulation import configure_sim_modes
from cylc.flow.subprocctx import SubFuncContext
from cylc.flow.subprocpool import get_xtrig_func
from cylc.flow.task_events_mgr import (
    EventData,
    get_event_handler_data
)
from cylc.flow.task_id import TaskID
from cylc.flow.task_outputs import (
    TASK_OUTPUT_SUCCEEDED,
    TaskOutputs
)
from cylc.flow.task_trigger import TaskTrigger, Dependency
from cylc.flow.taskdef import TaskDef
from cylc.flow.unicode_rules import (
    TaskNameValidator,
    TaskOutputValidator,
    TaskMessageValidator,
    XtriggerNameValidator,
)
from cylc.flow.wallclock import (
    get_current_time_string, set_utc_mode, get_utc_mode)
from cylc.flow.workflow_files import (
    NO_TITLE,
    WorkflowFiles,
    check_deprecation,
)
from cylc.flow.xtrigger_mgr import XtriggerManager

if TYPE_CHECKING:
    from optparse import Values
    from cylc.flow.cycling import IntervalBase, PointBase, SequenceBase

RE_CLOCK_OFFSET = re.compile(
    rf'''
        ^
        \s*
        ({TaskID.NAME_RE})   # task name
        (?:\(\s*(.+)\s*\))?  # optional (arguments, ...)
        \s*
        $
    ''',
    re.X,
)

RE_EXT_TRIGGER = re.compile(
    r'''
        ^
        \s*
        (.*)            # task name
        \s*
        \(\s*(.+)\s*\)  # required (arguments, ...)
        \s*
        $
    ''',
    re.X,
)
RE_SEC_MULTI_SEQ = re.compile(r'(?![^(]+\)),')
RE_WORKFLOW_ID_VAR = re.compile(r'\${?CYLC_WORKFLOW_(REG_)?ID}?')
RE_TASK_NAME_VAR = re.compile(r'\${?CYLC_TASK_NAME}?')
RE_VARNAME = re.compile(r'^[a-zA-Z_][\w]*$')


def check_varnames(env: Iterable[str]) -> List[str]:
    """Check a list of env var names for legality.

    Return a list of bad names (empty implies success).

    Examples:
        >>> check_varnames(['foo', 'BAR', '+baz'])
        ['+baz']

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

    Examples:
        >>> interpolate_template('_%(a)s_', {'a': 'A'})
        '_A_'

        >>> interpolate_template('%(a)s', {'b': 'B'})
        Traceback (most recent call last):
        cylc.flow.exceptions.ParamExpandError: bad parameter

        >>> interpolate_template('%(a)d', {'a': 'A'})
        Traceback (most recent call last):
        cylc.flow.exceptions.ParamExpandError: wrong data type for parameter

        >>> interpolate_template('%(as', {})
        Traceback (most recent call last):
        cylc.flow.exceptions.ParamExpandError: bad template syntax

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


def dequote(string):
    """Strip quotes off a string.

    Examples:
        >>> dequote('"foo"')
        'foo'
        >>> dequote("'foo'")
        'foo'
        >>> dequote('foo')
        'foo'
        >>> dequote('"f')
        '"f'
        >>> dequote('f')
        'f'

    """
    if len(string) < 2:
        return string
    if (string[0] == string[-1]) and string.startswith(("'", '"')):
        return string[1:-1]
    return string


class WorkflowConfig:
    """Class for workflow configuration items and derived quantities."""

    CHECK_CIRCULAR_LIMIT = 100  # If no. tasks > this, don't check circular
    VIS_N_POINTS = 3
    MAX_WARNING_LINES = 5

    def __init__(
        self,
        workflow: str,
        fpath: Union[Path, str],
        options: 'Values',
        template_vars: Optional[Mapping[str, Any]] = None,
        output_fname: Optional[str] = None,
        xtrigger_mgr: Optional[XtriggerManager] = None,
        mem_log_func: Optional[Callable[[str], None]] = None,
        run_dir: Optional[str] = None,
        log_dir: Optional[str] = None,
        work_dir: Optional[str] = None,
        share_dir: Optional[str] = None
    ) -> None:
        """
        Initialize the workflow config object.

        Args:
            workflow: workflow ID
            fpath: workflow config file path
            options: CLI options
        """
        check_deprecation(Path(fpath))
        self.mem_log = mem_log_func
        if self.mem_log is None:
            self.mem_log = lambda x: None
        self.mem_log("config.py:config.py: start init config")
        self.workflow = workflow
        self.workflow_name = get_workflow_name_from_id(self.workflow)
        self.fpath: Path = Path(fpath)
        self.fdir = str(self.fpath.parent)
        self.run_dir = run_dir
        self.log_dir = log_dir
        self.share_dir = share_dir
        self.work_dir = work_dir
        self.options = options
        self.implicit_tasks: Set[str] = set()
        self.edges: Dict[
            'SequenceBase', Set[Tuple[str, str, bool, bool]]
        ] = {}
        self.taskdefs: Dict[str, TaskDef] = {}
        self.expiration_offsets = {}
        self.ext_triggers = {}  # Old external triggers (client/server)
        self.xtrigger_mgr = xtrigger_mgr
        self.workflow_polling_tasks = {}  # type: ignore # TODO figure out type

        self.initial_point: 'PointBase'
        self.start_point: 'PointBase'
        self.stop_point: Optional['PointBase'] = None
        self.final_point: Optional['PointBase'] = None
        self.sequences: List['SequenceBase'] = []
        self.actual_first_point: Optional['PointBase'] = None
        self._start_point_for_actual_first_point: Optional['PointBase'] = None

        self.task_param_vars = {}  # type: ignore # TODO figure out type
        self.runahead_limit: Optional['IntervalBase'] = None

        # runtime hierarchy dicts keyed by namespace name:
        self.runtime: Dict[str, dict] = {  # TODO figure out type
            # lists of parent namespaces
            'parents': {},
            # lists of C3-linearized ancestor namespaces
            'linearized ancestors': {},
            # lists of first-parent ancestor namespaces
            'first-parent ancestors': {},
            # sets of all descendant namespaces
            # (not including the final tasks)
            'descendants': {},
            # sets of all descendant namespaces from the first-parent
            # hierarchy (first parents are collapsible in visualization)
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
            template_vars,
            self.options
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
        self.check_for_owner(self.cfg['runtime'])
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
        self.process_stop_cycle_point()

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
                    if (
                        cylc.flow.flags.verbosity > 0
                        and offset_string.startswith("-")
                    ):
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
                        if s_type == 'clock-expire':
                            self.expiration_offsets[member] = offset_interval
                        if s_type == 'external-trigger':
                            self.ext_triggers[member] = ext_trigger_msg
                elif s_type == 'clock-expire':
                    self.expiration_offsets[name] = offset_interval
                elif s_type == 'external-trigger':
                    self.ext_triggers[name] = dequote(ext_trigger_msg)

            self.cfg['scheduling']['special tasks'][s_type] = result

        self.process_config_env()

        self.mem_log("config.py: before load_graph()")
        self.load_graph()
        self.mem_log("config.py: after load_graph()")

        self.process_runahead_limit()

        if self.run_mode('simulation', 'dummy'):
            configure_sim_modes(
                self.taskdefs.values(), self.run_mode())

        self.configure_workflow_state_polling_tasks()

        self._check_task_event_handlers()
        self._check_special_tasks()  # adds to self.implicit_tasks
        self._check_explicit_cycling()

        self._warn_if_queues_have_implicit_tasks(
            self.cfg, self.taskdefs, self.MAX_WARNING_LINES)

        self._check_implicit_tasks()
        self._check_sequence_bounds()
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

        self.upgrade_clock_triggers()

        self.leaves = self.get_task_name_list()
        for ancestors in self.runtime['first-parent ancestors'].values():
            try:
                foot = ancestors[-2]  # one back from 'root'
            except IndexError:
                pass
            else:
                if foot not in self.feet:
                    self.feet.append(foot)
        self.feet.sort()  # sort effects get_graph_raw output

        self.process_metadata_urls()

        if getattr(self.options, 'is_validate', False):
            self.mem_log("config.py: before _check_circular()")
            self._check_circular()
            self.mem_log("config.py: after _check_circular()")

        self.mem_log("config.py: end init config")

    @staticmethod
    def _warn_if_queues_have_implicit_tasks(
        config, taskdefs, max_warning_lines
    ):
        """Warn if queues contain implict tasks.
        """
        implicit_q_msg = ''

        # Get the names of the first N implicit queue tasks:
        for queue in config["scheduling"]["queues"]:
            for name in config["scheduling"]["queues"][queue][
                "members"
            ]:
                if (
                    name not in taskdefs
                    and name not in config['runtime']
                    and len(implicit_q_msg.split('\n')) <= max_warning_lines
                ):
                    implicit_q_msg += f'\n * task {name!r} in queue {queue!r}'

        # Warn users if tasks are implied by queues.
        if implicit_q_msg:
            truncation_msg = (
                f"\n...showing first {max_warning_lines} tasks..."
                if len(implicit_q_msg.split('\n')) > max_warning_lines
                else ""
            )
            LOG.warning(
                'Queues contain tasks not defined in'
                f' runtime: {implicit_q_msg}{truncation_msg}'
            )

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
        if (
            not cylc.flow.flags.cylc7_back_compat
            and not cfg_cp_tz
        ):
            cfg_cp_tz = 'Z'
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

    def process_initial_cycle_point(self) -> None:
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
            # now/next()/previous() was used, need to store
            # evaluated point in DB
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

    def process_start_cycle_point(self) -> None:
        """Set the start cycle point from options.

        Sets:
            self.options.startcp
            self.start_point
        """
        startcp = getattr(self.options, 'startcp', None)
        starttask = getattr(self.options, 'starttask', None)

        if startcp is not None and starttask is not None:
            raise InputError(
                "--start-cycle-point and --start-task are mutually exclusive"
            )
        if startcp:
            # Start from a point later than initial point.
            if self.options.startcp == 'now':
                self.options.startcp = get_current_time_string()
            self.start_point = get_point(self.options.startcp).standardise()
        elif starttask:
            # Start from designated task(s).
            # Select the earliest start point for use in pre-initial ignore.
            try:
                cycle_points = [
                    Tokens(taskid, relative=True)['cycle']
                    for taskid in self.options.starttask
                ]
            except ValueError as exc:
                raise InputError(str(exc))
            self.start_point = min(
                get_point(cycle).standardise()
                for cycle in cycle_points if cycle
            )
        else:
            # Start from the initial point.
            self.start_point = self.initial_point

    def process_final_cycle_point(self) -> None:
        """Validate and set the final cycle point from flow.cylc or options.

        Sets:
            self.final_point
            self.cfg['scheduling']['final cycle point']
        Raises:
            WorkflowConfigError - if it fails to validate
        """
        if self.cfg['scheduling']['final cycle point'] == '':
            # (Unlike other cycle point settings in config, fcp is treated as
            # a string by parsec to allow for expressions like '+P1Y')
            self.cfg['scheduling']['final cycle point'] = None
        fcp_str = getattr(self.options, 'fcp', None)
        if fcp_str == 'reload':
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
                with suppress(IsodatetimeError):
                    # Relative, ISO8601 cycling.
                    self.final_point = get_point_relative(
                        fcp_str, self.initial_point).standardise()
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

    def process_stop_cycle_point(self) -> None:
        """Set the stop after cycle point.

        In decreasing priority, it is set:
        * From the command line option (``--stopcp=XYZ``) or database.
        * From the flow.cylc file (``[scheduling]stop after cycle point``).

        However, if ``--stopcp=reload`` on the command line during restart,
        the ``[scheduling]stop after cycle point`` value is used.
        """
        stopcp_str: Optional[str] = getattr(self.options, 'stopcp', None)
        if stopcp_str == 'reload':
            stopcp_str = self.options.stopcp = None
        if stopcp_str is None:
            stopcp_str = self.cfg['scheduling']['stop after cycle point']

        if stopcp_str is not None:
            self.stop_point = get_point(stopcp_str).standardise()
            if self.final_point and (self.stop_point > self.final_point):
                LOG.warning(
                    f"Stop cycle point '{self.stop_point}' will have no "
                    "effect as it is after the final cycle "
                    f"point '{self.final_point}'."
                )
                self.stop_point = None
            stopcp_str = str(self.stop_point) if self.stop_point else None
            self.cfg['scheduling']['stop after cycle point'] = stopcp_str

    def _check_implicit_tasks(self) -> None:
        """Raise WorkflowConfigError if implicit tasks are found in graph or
        queue config, unless allowed by config."""
        if not self.implicit_tasks:
            return
        print_limit = 10
        tasks_str = '\n    * '.join(list(self.implicit_tasks)[:print_limit])
        num = len(self.implicit_tasks)
        if num > print_limit:
            tasks_str += f"\n    and {num} more"
        msg = (
            "implicit tasks detected (no entry under [runtime]):\n"
            f"    * {tasks_str}"
        )
        if self.cfg['scheduler']['allow implicit tasks']:
            LOG.debug(msg)
            return

        # Check if implicit tasks explicitly disallowed
        try:
            is_disallowed = self.pcfg.get(
                ['scheduler', 'allow implicit tasks'], sparse=True
            ) is False
        except ItemNotFoundError:
            is_disallowed = False
        if is_disallowed:
            raise WorkflowConfigError(msg)
        # Otherwise "[scheduler]allow implicit tasks" is not set

        if not cylc.flow.flags.cylc7_back_compat:
            msg += (
                "\nTo allow implicit tasks, use "
                f"'{WorkflowFiles.FLOW_FILE}[scheduler]allow implicit tasks'"
            )
        # Allow implicit tasks in back-compat mode unless rose-suite.conf
        # present (to maintain compat with Rose 2019)
        elif not (self.fpath.parent / "rose-suite.conf").is_file():
            LOG.debug(msg)
            return

        raise WorkflowConfigError(msg)

    def _check_circular(self):
        """Check for circular dependence in graph."""
        if (len(self.taskdefs) > self.CHECK_CIRCULAR_LIMIT and
                not getattr(self.options, 'check_circular', False)):
            LOG.warning(
                f"Number of tasks is > {self.CHECK_CIRCULAR_LIMIT}; will not "
                "check graph for circular dependencies. To enforce this "
                "check, use the option --check-circular.")
            return
        start_point_str = self.cfg['scheduling']['initial cycle point']
        raw_graph = self.get_graph_raw(start_point_str,
                                       stop_point_str=None)
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
                        Tokens(
                            cycle=str(lhs[1]),
                            task=lhs[0]
                        ).relative_id,
                        Tokens(
                            cycle=str(rhs[1]),
                            task=rhs[0]
                        ).relative_id,
                    )
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
        sxs = set(x2ys).difference(y2xs)
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

    def _check_sequence_bounds(self):
        """Check bounds of sequences against the start point."""
        out_of_bounds = [
            str(seq)
            for seq in self.sequences
            if seq.get_first_point(self.start_point) is None
        ]
        if out_of_bounds:
            if len(out_of_bounds) > 1:
                # avoid spamming users with multiple warnings
                out_of_bounds_str = '\n'.join(
                    wrap(', '.join(out_of_bounds), 70))
                msg = (
                    "multiple sequences out of bounds for"
                    " initial cycle point "
                    f"{self.start_point}:\n{out_of_bounds_str}"
                )
            else:
                msg = (
                    f"{out_of_bounds[0]}: sequence out of bounds for "
                    f"initial cycle point {self.start_point}"
                )
            LOG.warning(msg)

    def _expand_name_list(self, orig_names):
        """Expand any parameters in lists of names."""
        name_expander = NameExpander(self.parameters)
        exp_names = []
        for orig_name in orig_names:
            exp_names += [name for name, _ in name_expander.expand(orig_name)]
        return exp_names

    def _update_task_params(self, task_name, params):
        """Update the dict of parameters used in a task definition.

        # Used to expand parameter values in task environments.
        """
        self.task_param_vars.setdefault(
            task_name, {}
        ).update(
            params
        )

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
                    self._update_task_params(name, indices)
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
                        used_indices, expanded = (
                            name_expander.expand_parent_params(
                                parent, indices, origin)
                        )
                        repl_parents.append(expanded)
                        if used_indices:
                            self._update_task_params(name, used_indices)
                    newruntime[name]['inherit'] = repl_parents
        self.cfg['runtime'] = newruntime

    def validate_namespace_names(self):
        """Validate task and family names."""
        for name in self.implicit_tasks:
            success, message = TaskNameValidator.validate(name)
            if not success:
                raise WorkflowConfigError(
                    f'invalid task name "{name}"\n{message}'
                )
        for name in self.cfg['runtime']:
            if name == 'root':
                # root is allowed to be defined in the runtime section
                continue
            success, message = TaskNameValidator.validate(name)
            if not success:
                raise WorkflowConfigError(
                    f'task/family name {message}\n[runtime][[{name}]]'
                )

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
            raise WorkflowConfigError(
                "Illegal environment variable name(s) detected:\n* "
                # f"\n{err_msg}"
                + '\n* '.join(
                    f'[runtime][{label}][{key}]{name}'
                    for (label, key), names in bad.items()
                    for name in names
                )
            )

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
                + '\n    '.join(
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
                self.runtime['descendants'].setdefault(p, set()).add(name)
            first_ancestors = self.runtime['first-parent ancestors'][name]
            for p in first_ancestors[1:]:
                self.runtime['first-parent descendants'].setdefault(
                    p, set()
                ).add(name)

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
        """Extract runahead limit information."""
        limit = self.cfg['scheduling']['runahead limit']
        if limit.isdigit():
            limit = f'PT{limit}H'
            LOG.warning(
                'Use of a raw number of hours for the runahead limit is '
                f'deprecated. Use "{limit}" instead')

        number_limit_regex = re.compile(r'^P\d+$')
        time_limit_regexes = DurationParser.DURATION_REGEXES

        if number_limit_regex.fullmatch(limit):
            self.runahead_limit = IntegerInterval(limit)
        elif (  # noqa: SIM106
            self.cycling_type == ISO8601_CYCLING_TYPE
            and any(tlr.fullmatch(limit) for tlr in time_limit_regexes)
        ):
            self.runahead_limit = ISO8601Interval(limit)
        else:
            raise WorkflowConfigError(
                f'bad runahead limit "{limit}" for {self.cycling_type} '
                'cycling type')

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
                f" --task={tdef.workflow_polling_cfg['task']}"
                " --point=$CYLC_TASK_CYCLE_POINT"
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
                tree[key] = self.cfg['runtime'][key]['meta'].get(
                    'title', NO_TITLE)
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
            result[ns] = self.cfg['runtime'][ns]['meta'].get(
                'title', NO_TITLE)

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
        """Export Workflow context to the local environment.

        A source workflow has only a name.
        Once installed it also has an ID and a run directory.
        And at scheduler start-up it has work, share, and log sub-dirs too.
        """
        for key, value in {
            **verbosity_to_env(cylc.flow.flags.verbosity),
            'CYLC_WORKFLOW_NAME': self.workflow_name,
            'CYLC_WORKFLOW_NAME_BASE': str(Path(self.workflow_name).name),
        }.items():
            os.environ[key] = value

        if is_relative_to(self.fdir, get_cylc_run_dir()):
            # This is an installed workflow.
            #  - self.run_dir is only defined by the scheduler
            #  - but the run dir exists, created at installation
            #  - run sub-dirs may exist, if this installation was run already
            #    but if the scheduler is not running they shouldn't be used.
            for key, value in {
                'CYLC_WORKFLOW_ID': self.workflow,
                'CYLC_WORKFLOW_RUN_DIR': str(self.fdir),
            }.items():
                os.environ[key] = value

        if self.run_dir is not None:
            # Run directory is only defined if the scheduler is running; in
            # which case the following run sub-directories must exist.
            for key, value in {
                'CYLC_WORKFLOW_LOG_DIR': str(self.log_dir),
                'CYLC_WORKFLOW_WORK_DIR': str(self.work_dir),
                'CYLC_WORKFLOW_SHARE_DIR': str(self.share_dir),
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
                            key == 'handlers' or key.endswith(' handlers')):
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
        """Return a sorted list of all tasks used in the dependency graph.

        Note: the sort order may effect get_graph_raw ouput.

        """
        return sorted(self.taskdefs)

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

    def generate_taskdef(self, orig_expr, node):
        """Generate task definition for node."""
        name = GraphNodeParser.get_inst().parse(node)[0]
        taskdef = self.get_taskdef(name, orig_expr)
        if name in self.workflow_polling_tasks:
            taskdef.workflow_polling_cfg = {
                'workflow': self.workflow_polling_tasks[name][0],
                'task': self.workflow_polling_tasks[name][1],
                'status': self.workflow_polling_tasks[name][2]
            }

    def add_sequence(self, nodes, seq, suicide):
        """Add valid sequences to taskdefs."""
        for node in nodes:
            name, offset = GraphNodeParser.get_inst().parse(node)[:2]
            taskdef = self.get_taskdef(name)
            # Only add sequence to taskdef if explicit (not an offset).
            if offset:
                taskdef.used_in_offset_trigger = True
            elif not suicide:
                # "foo => !bar" does not define a sequence for bar
                taskdef.add_sequence(seq)

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
                # Qualifier is a custom task message.
                qualifier = outputs[output]
            elif output:
                if not TaskOutputs.is_valid_std_name(output):
                    raise WorkflowConfigError(
                        f"Undefined custom output: {name}:{output}"
                    )
                qualifier = output
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
                if label != 'wall_clock':
                    raise WorkflowConfigError(f"xtrigger not defined: {label}")
                else:
                    # Allow "@wall_clock" in graph as implicit zero-offset.
                    xtrig = SubFuncContext('wall_clock', 'wall_clock', [], {})

            if (
                xtrig.func_name == 'wall_clock'
                and self.cycling_type == INTEGER_CYCLING_TYPE
            ):
                raise WorkflowConfigError(
                    "Clock xtriggers require datetime cycling:"
                    f" {label} = {xtrig.get_signature()}"
                )

            # Generic xtrigger validation.
            XtriggerManager.check_xtrigger(label, xtrig, self.fdir)

            # Specific xtrigger.validate(), if available.
            with suppress(AttributeError, ImportError):
                get_xtrig_func(xtrig.func_name, "validate", self.fdir)(
                    xtrig.func_args,
                    xtrig.func_kwargs,
                    xtrig.get_signature()
                )

            if self.xtrigger_mgr:
                # (not available during validation)
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

    def _get_stop_point(self, start_point, stop_point_str=None):
        """Get stop point from string value or interval, or return None."""
        if stop_point_str is None:
            stop_point = None
        elif "P" in stop_point_str:
            # Is the final point(/interval) relative to initial?
            if self.cfg['scheduling']['cycling mode'] == 'integer':
                # Relative, integer cycling.
                stop_point = get_point_relative(
                    stop_point_str, start_point
                ).standardise()
            else:
                # Relative, ISO8601 cycling.
                stop_point = get_point_relative(
                    stop_point_str, start_point
                ).standardise()
        else:
            stop_point = get_point(stop_point_str).standardise()
        return stop_point

    def get_graph_raw(
            self, start_point_str=None, stop_point_str=None, grouping=None):
        """Return concrete graph edges between specified cycle points.

        Return a family-collapsed graph if the grouping arg is not None:
          * ['FAM1', 'FAM2']: group (collapse) specified families
          * ['<all>']: group (collapse) all families above root

        For validation, return non-suicide edges with left and right nodes.
        """
        start_point = get_point(
            start_point_str or
            self.cfg['scheduling']['initial cycle point']
        )
        stop_point = self._get_stop_point(start_point, stop_point_str)

        actual_first_point = self.get_actual_first_point(start_point)

        if grouping is None:
            grouping = []
        elif grouping == ['<all>']:
            grouping = [
                fam for
                fam in self.runtime["first-parent descendants"].keys()
                if fam != "root"
            ]
        else:
            for bad in (
                set(grouping).difference(
                    self.runtime["first-parent descendants"].keys()
                )
            ):
                LOG.warning(f"Ignoring undefined family {bad}")
                grouping.remove(bad)

        is_validate = getattr(
            self.options, 'is_validate', False)  # this is for _check_circular
        if is_validate:
            grouping = []

        # Now define the concrete graph edges (pairs of nodes) for plotting.

        workflow_final_point = get_point(
            self.cfg['scheduling']['final cycle point'])

        # For the computed stop point, store VIS_N_POINTS of each sequence,
        # and then cull later to the first VIS_N_POINTS over all sequences.

        # For nested closed families, only consider the outermost one
        fpd = self.runtime['first-parent descendants']
        clf_map = {}
        for name in grouping:
            if all(
                name not in fpd[i]
                for i in grouping
            ):
                clf_map[name] = fpd[name]

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
                if stop_point is None and len(new_points) > self.VIS_N_POINTS:
                    # Take VIS_N_POINTS cycles from each sequence.
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
                        # @xtrigger node.
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
        if stop_point is None:
            # Prune to VIS_N_POINTS points in total.
            graph_raw_edges = []
            for point in sorted(gr_edges)[:self.VIS_N_POINTS]:
                graph_raw_edges.extend(gr_edges[point])
        else:
            # Flatten nested list.
            graph_raw_edges = (
                [i for sublist in gr_edges.values() for i in sublist])
        graph_raw_edges.sort(key=lambda x: [y if y else '' for y in x[:2]])
        return graph_raw_edges

    def get_node_labels(self, start_point_str=None, stop_point_str=None):
        """Return dependency graph node labels."""
        ret = set()
        for edge in self.get_graph_raw(
                start_point_str,
                stop_point_str,
        ):
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
            lret = Tokens(
                cycle=str(lpoint),
                task=lname,
            ).relative_id
        rret = None
        rname, rpoint = None, None
        if r_id:
            rname, rpoint = r_id
            rret = Tokens(
                cycle=str(rpoint),
                task=rname,
            ).relative_id

        for fam_name, fam_members in clf_map.items():
            if lname in fam_members and rname in fam_members:
                # l and r are both members
                lret = Tokens(
                    cycle=str(lpoint),
                    task=fam_name,
                ).relative_id
                rret = Tokens(
                    cycle=str(rpoint),
                    task=fam_name,
                ).relative_id
                break
            elif lname in fam_members:
                # l is a member
                lret = Tokens(
                    cycle=str(lpoint),
                    task=fam_name,
                ).relative_id
            elif rname in fam_members:
                # r is a member
                rret = Tokens(
                    cycle=str(rpoint),
                    task=fam_name,
                ).relative_id

        return lret, rret

    def load_graph(self):
        """Parse and load dependency graph."""
        LOG.debug("Parsing the dependency graph")

        # Generate a map of *task* members of each family.
        # Note we could exclude 'root' from this and disallow use of 'root' in
        # the graph (which would probably be quite reasonable).
        family_map = {
            family: [
                task for task in sorted(tasks)
                if (
                    task in self.runtime['parents'] and
                    task not in self.runtime['descendants']
                )
            ]
            for family, tasks in self.runtime['descendants'].items()
            if family != 'root'
        }

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
        task_output_opt = {}
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
            parser = GraphParser(
                family_map,
                self.parameters,
                task_output_opt=task_output_opt
            )
            parser.parse_graph(graph)
            task_output_opt.update(parser.task_output_opt)
            self.workflow_polling_tasks.update(
                parser.workflow_state_polling_tasks)
            self._proc_triggers(parser, seq, task_triggers)

        self.set_required_outputs(task_output_opt)

        # Detect use of xtrigger names with '@' prefix (creates a task).
        overlap = set(self.taskdefs.keys()).intersection(
            list(self.cfg['scheduling']['xtriggers']))
        if overlap:
            LOG.error(', '.join(overlap))
            raise WorkflowConfigError('task and @xtrigger names clash')

        for tdef in self.taskdefs.values():
            tdef.tweak_outputs()

    def _proc_triggers(self, parser, seq, task_triggers):
        """Define graph edges, taskdefs, and triggers, from graph sections."""
        suicides = 0
        for right, val in parser.triggers.items():
            for expr, trigs in val.items():
                orig = parser.original[right][expr]
                lefts, suicide = trigs

                # (lefts, right) e.g.:
                # for """
                #    foo|bar => baz
                #    @x => baz
                # """
                # - ([], foo)
                # - ([], bar)
                # - (['foo:succeeded', 'bar:succeeded'], baz)
                # - (['@x'], baz)
                self.generate_edges(expr, orig, lefts, right, seq, suicide)

                # Lefts can be null; all appear on RHS once so can generate
                # taskdefs with right only. Right is never None or @xtrigger.
                self.generate_taskdef(orig, right)

                self.add_sequence(
                    [
                        node
                        for node in lefts + [right]
                        if node and not node.startswith('@')
                    ],
                    seq,
                    suicide
                )

                # RHS quals not needed now (used already for taskdef outputs)
                right = parser.REC_QUAL.sub('', right)
                self.generate_triggers(
                    expr, lefts, right, seq, suicide, task_triggers)
                if suicide:
                    suicides += 1

        if suicides and not cylc.flow.flags.cylc7_back_compat:
            LOG.warning(
                f"{suicides} suicide trigger(s) detected. These are rarely "
                "needed in Cylc 8 - see https://cylc.github.io/cylc-doc/"
                "stable/html/7-to-8/major-changes/suicide-triggers.html"
            )

    def set_required_outputs(
        self, task_output_opt: Dict[Tuple[str, str], Tuple[bool, bool, bool]]
    ) -> None:
        """set optional/required status of parsed task outputs.

        Args:
            task_output_opt: {(task, output): (is-optional, default, is_set)}
        """
        for name, taskdef in self.taskdefs.items():
            for output in taskdef.outputs:
                try:
                    optional, _, _ = task_output_opt[(name, output)]
                except KeyError:
                    # Output not used in graph.
                    continue
                taskdef.set_required_output(output, not optional)

    def find_taskdefs(self, name: str) -> Set[TaskDef]:
        """Find TaskDef objects in family "name" or matching "name".

        Return a list of TaskDef objects which:
        * have names that glob matches "name".
        * are in a family that glob matches "name".
        """
        if name in self.taskdefs:
            # Match a task name
            return {self.taskdefs[name]}

        fams = self.runtime['first-parent descendants']
        if name in fams:
            # Match a family name
            return {
                self.taskdefs[member] for member in fams[name]
                if member in self.taskdefs
            }

        # Glob match
        from_task_names = {
            taskdef for key, taskdef in self.taskdefs.items()
            if fnmatchcase(key, name)
        }
        from_family_names = {
            self.taskdefs[member]
            for key, members in fams.items()
            if fnmatchcase(key, name)
            for member in members
            if member in self.taskdefs
        }
        return from_task_names.union(from_family_names)

    def get_taskdef(
        self, name: str, orig_expr: Optional[str] = None
    ) -> TaskDef:
        """Return an instance of TaskDef for task name."""
        if name not in self.taskdefs:
            if name == 'root':
                self.implicit_tasks.add(name)
            elif name not in self.cfg['runtime']:
                # implicit inheritance from root
                self.implicit_tasks.add(name)
                # These can't just be a reference to root runtime as we have to
                # make some items task-specific: e.g. subst task name in URLs.
                self.cfg['runtime'][name] = OrderedDictWithDefaults()
                replicate(self.cfg['runtime'][name],
                          self.cfg['runtime']['root'])
                if 'root' not in self.runtime['descendants']:
                    # (happens when no runtimes are defined in flow.cylc)
                    self.runtime['descendants']['root'] = set()
                if 'root' not in self.runtime['first-parent descendants']:
                    # (happens when no runtimes are defined in flow.cylc)
                    self.runtime['first-parent descendants']['root'] = set()
                self.runtime['parents'][name] = ['root']
                self.runtime['linearized ancestors'][name] = [name, 'root']
                self.runtime['first-parent ancestors'][name] = [name, 'root']
                self.runtime['descendants']['root'].add(name)
                self.runtime['first-parent descendants']['root'].add(name)
                self.ns_defn_order.append(name)

            try:
                self.taskdefs[name] = self._get_taskdef(name)
            except TaskDefError as exc:
                if orig_expr:
                    LOG.error(orig_expr)
                raise WorkflowConfigError(str(exc))
            else:
                # Record custom message outputs from [runtime].
                for output, message in (
                    self.cfg['runtime'][name]['outputs'].items()
                ):
                    valid, msg = TaskOutputValidator.validate(output)
                    if not valid:
                        raise WorkflowConfigError(
                            f'Invalid task output "'
                            f'[runtime][{name}][outputs]'
                            f'{output} = {message}" - {msg}'
                        )
                    valid, msg = TaskMessageValidator.validate(message)
                    if not valid:
                        raise WorkflowConfigError(
                            f'Invalid task message "'
                            f'[runtime][{name}][outputs]'
                            f'{output} = {message}" - {msg}'
                        )
                    self.taskdefs[name].add_output(output, message)

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

    def process_metadata_urls(self):
        """Process [meta]URL items."""
        # workflow metadata
        url = self.cfg['meta']['URL']
        try:
            self.cfg['meta']['URL'] = url % {
                'workflow': self.workflow,
            }
        except (KeyError, ValueError):
            try:
                # Replace workflow and task name in workflow and task URLs.
                # BACK COMPAT: suite_name
                # url:
                #     https://github.com/cylc/cylc-flow/pull/4724
                # from:
                #     Cylc7
                # to:
                #     Cylc8
                # remove at:
                #     Cylc8.x
                self.cfg['meta']['URL'] = url % {
                    # cylc 7
                    'suite_name': self.workflow,
                    # cylc 8
                    'workflow': self.workflow,
                }
            except (KeyError, ValueError):
                raise InputError(f'Invalid template [meta]URL: {url}')
            else:
                LOG.warning(
                    'Detected deprecated template variables in [meta]URL.'
                    '\nSee the configuration documentation for details.'
                )

        # task metadata
        self.cfg['meta']['URL'] = RE_WORKFLOW_ID_VAR.sub(
            self.workflow, self.cfg['meta']['URL'])
        for name, cfg in self.cfg['runtime'].items():
            try:
                cfg['meta']['URL'] = cfg['meta']['URL'] % {
                    'workflow': self.workflow,
                    'task': name,
                }
            except (KeyError, ValueError):
                # BACK COMPAT: suite_name, task_name
                # url:
                #     https://github.com/cylc/cylc-flow/pull/4724
                # from:
                #     Cylc7
                # to:
                #     Cylc8
                # remove at:
                #     Cylc8.x
                try:
                    cfg['meta']['URL'] = cfg['meta']['URL'] % {
                        # cylc 7
                        'suite_name': self.workflow,
                        'task_name': name,
                        # cylc 8
                        'workflow': self.workflow,
                        'task': name,
                    }
                except (KeyError, ValueError):
                    raise InputError(f'Invalid template [meta]URL: {url}')
                else:
                    LOG.warning(
                        'Detected deprecated template variables in'
                        f' [runtime][{name}][meta]URL.'
                        '\nSee the configuration documentation for details.'
                    )
            cfg['meta']['URL'] = RE_WORKFLOW_ID_VAR.sub(
                self.workflow, cfg['meta']['URL'])
            cfg['meta']['URL'] = RE_TASK_NAME_VAR.sub(
                name, cfg['meta']['URL'])

    @staticmethod
    def check_for_owner(tasks: Dict) -> None:
        """Raise exception if [runtime][task][remote]owner
        """
        owners = {}
        for task, tdef in tasks.items():
            owner = tdef.get('remote', {}).get('owner', None)
            if owner:
                owners[task] = owner
        if owners:
            # TODO: Convert URL to a stable or latest release doc after 8.0
            # https://github.com/cylc/cylc-flow/issues/4663
            msg = (
                '"[runtime][task][remote]owner" is obsolete at Cylc 8.'
                '\nsee https://cylc.github.io/cylc-doc/stable/'
                'html/7-to-8/major-changes/remote-owner.html'
                f'\nFirst {min(len(owners), 5)} tasks:'
            )
            for task, _ in list(owners.items())[:5]:
                msg += f'\n  * {task}"'
            raise WorkflowConfigError(msg)

    def upgrade_clock_triggers(self):
        """Convert old-style clock triggers to clock xtriggers.

        [[special tasks]]
           clock-trigger = foo(PT1D)

        becomes:

        [[xtriggers]]
           _cylc_wall_clock_foo = wallclock(PT1D)

        Not done by parsec upgrade because the graph has to be parsed first.
        """
        for item in self.cfg['scheduling']['special tasks']['clock-trigger']:
            match = RE_CLOCK_OFFSET.match(item)
            # (Already validated during "special tasks" parsing above.)
            task_name, offset = match.groups()
            # Derive an xtrigger label.
            label = '_'.join(('_cylc', 'wall_clock', task_name))
            # Define the xtrigger function.
            xtrig = SubFuncContext(label, 'wall_clock', [], {})
            xtrig.func_kwargs["offset"] = offset
            if self.xtrigger_mgr is None:
                XtriggerManager.check_xtrigger(label, xtrig, self.fdir)
            else:
                self.xtrigger_mgr.add_trig(label, xtrig, self.fdir)
            # Add it to the task, for each sequence that the task appears in.
            taskdef = self.get_taskdef(task_name)
            for seq in taskdef.sequences:
                taskdef.add_xtrig_label(label, seq)
