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
"""Manage the workflow data store.

The data store is generated here, in a Workflow Service (WS), and synced to the
User Interface Server (UIS) via protobuf messages. Used as resolving data with
GraphQL, both in the WS and UIS, it is then provisioned to the CLI and GUI.

This data store is comprised of Protobuf message objects (data elements),
which are used as data containers for their respective type.

Changes to the data store are accumulated on a main loop iteration as deltas
in the form of protobuf messages, and then applied to the local data-store.
These deltas are populated with the minimal information; only the elements
and only the fields of those elements that have changed. It is done this way
for the efficient transport and consistent application to remotely synced
data-stores.

Static data elements are generated on workflow start/restart/reload, which
includes workflow, task, and family definition objects.

The cycle point nodes/edges (i.e. task/family proxies) generation is triggered
individually on transition to active task pool. Each active task is generated
along with any children and parents via a graph walk out to a specified maximum
graph distance (n_edge_distance), that can be externally altered (via API).
Collectively this forms the N-Distance-Window on the workflow graph.

Pruning of data-store elements is done using the collection/set of nodes
generated at the boundary of an active node's graph walk and registering active
node's parents against them. Once active, these boundary nodes act as the prune
triggers for the associated parent nodes. Set operations are used to do a diff
between the nodes of active paths (paths whose node is in the active task pool)
and the nodes of flagged paths (whose boundary node(s) have become active).

Updates are created by the event/task/job managers.

Data elements include a "stamp" field, which is a timestamped ID for use
in assessing changes in the data store, for comparisons of a store sync.

Packaging methods are included for dissemination of protobuf messages.

"""

from contextlib import suppress
from collections import Counter, deque
from copy import deepcopy
import json
from time import time
from typing import (
    Any,
    Dict,
    Optional,
    List,
    Set,
    TYPE_CHECKING,
    Tuple,
    Union,
)
import zlib

from cylc.flow import __version__ as CYLC_VERSION, LOG
from cylc.flow.cycling.loader import get_point
from cylc.flow.data_messages_pb2 import (
    PbEdge, PbEntireWorkflow, PbFamily, PbFamilyProxy, PbJob, PbTask,
    PbTaskProxy, PbWorkflow, PbRuntime, AllDeltas, EDeltas, FDeltas,
    FPDeltas, JDeltas, TDeltas, TPDeltas, WDeltas)
from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.id import Tokens
from cylc.flow.network import API
from cylc.flow.parsec.util import (
    listjoin,
    pdeepcopy,
    poverride
)
from cylc.flow.workflow_status import (
    get_workflow_status,
    get_workflow_status_msg,
)
from cylc.flow.task_job_logs import JOB_LOG_OPTS, get_task_job_log
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_state import (
    TASK_STATUS_WAITING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_STATUSES_ORDERED
)
from cylc.flow.task_state_prop import extract_group_state
from cylc.flow.taskdef import generate_graph_parents, generate_graph_children
from cylc.flow.task_state import TASK_STATUSES_FINAL
from cylc.flow.util import (
    serialise_set,
    deserialise_set
)
from cylc.flow.wallclock import (
    TIME_ZONE_LOCAL_INFO,
    TIME_ZONE_UTC_INFO,
    get_utc_mode
)

if TYPE_CHECKING:
    from cylc.flow.cycling import PointBase
    from cylc.flow.flow_mgr import FlowNums

EDGES = 'edges'
FAMILIES = 'families'
FAMILY_PROXIES = 'family_proxies'
JOBS = 'jobs'
TASKS = 'tasks'
TASK_PROXIES = 'task_proxies'
WORKFLOW = 'workflow'
ALL_DELTAS = 'all'
DELTA_ADDED = 'added'
DELTA_UPDATED = 'updated'
DELTA_PRUNED = 'pruned'
LATEST_STATE_TASKS_QUEUE_SIZE = 5

MESSAGE_MAP = {
    EDGES: PbEdge,
    FAMILIES: PbFamily,
    FAMILY_PROXIES: PbFamilyProxy,
    JOBS: PbJob,
    TASKS: PbTask,
    TASK_PROXIES: PbTaskProxy,
    WORKFLOW: PbWorkflow,
}

DATA_TEMPLATE = {
    EDGES: {},
    FAMILIES: {},
    FAMILY_PROXIES: {},
    JOBS: {},
    TASKS: {},
    TASK_PROXIES: {},
    WORKFLOW: PbWorkflow(),
}

DELTAS_MAP = {
    EDGES: EDeltas,
    FAMILIES: FDeltas,
    FAMILY_PROXIES: FPDeltas,
    JOBS: JDeltas,
    TASKS: TDeltas,
    TASK_PROXIES: TPDeltas,
    WORKFLOW: WDeltas,
    ALL_DELTAS: AllDeltas,
}

DELTA_FIELDS = {DELTA_ADDED, DELTA_UPDATED, DELTA_PRUNED}

JOB_STATUSES_ALL = [
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
]

# Faster lookup where order not needed.
JOB_STATUS_SET = set(JOB_STATUSES_ALL)

# Protobuf message merging appends repeated field results on merge,
# unlike singular fields which are overwritten. This behaviour is
# desirable in many cases, but there are exceptions.
# The following is used to flag which fields require clearing before
# merging from respective deltas messages.
CLEAR_FIELD_MAP = {
    EDGES: set(),
    FAMILIES: set(),
    FAMILY_PROXIES: {'state_totals', 'states'},
    JOBS: {'messages'},
    TASKS: set(),
    TASK_PROXIES: {'prerequisites'},
    WORKFLOW: {'latest_state_tasks', 'state_totals', 'states'},
}


def setbuff(obj, key, value):
    """Set an attribute on a protobuf object.

    Although `None` is a valid value for an `optional` field in protobuf e.g:

       >>> job = PbJob(job_id=None)

    Attempting to set a field to none after initiation results in error:

       >>> job.job_id = None
       Traceback (most recent call last):
       TypeError: ...

    For safety this method only sets the attribute if the value is not None.

    Note:
        If the above doctest fails, then the behaviour of protobuf has changed
        and this wrapper might not be necessary any more.

    See:
        https://github.com/cylc/cylc-flow/issues/5388

    Example:
        >>> from types import SimpleNamespace
        >>> obj = SimpleNamespace()
        >>> setbuff(obj, 'a', 1); obj
        namespace(a=1)
        >>> setbuff(obj, 'b', None); obj
        namespace(a=1)

    """
    if value is not None:
        setattr(obj, key, value)


def generate_checksum(in_strings):
    """Generate cross platform & python checksum from strings."""
    # can't use hash(), it's not the same across 32-64bit or python invocations
    return zlib.adler32(''.join(sorted(in_strings)).encode()) & 0xffffffff


def task_mean_elapsed_time(tdef):
    """Calculate task mean elapsed time."""
    if tdef.elapsed_times:
        return round(sum(tdef.elapsed_times) / len(tdef.elapsed_times))
    return tdef.rtconfig.get('execution time limit', None)


def runtime_from_config(rtconfig):
    """Populate runtime object from config."""
    try:
        platform = rtconfig['platform']['name']
    except (KeyError, TypeError):
        platform = rtconfig['platform']
    directives = rtconfig['directives']
    environment = rtconfig['environment']
    outputs = rtconfig['outputs']
    return PbRuntime(
        platform=platform,
        script=rtconfig['script'],
        completion=rtconfig['completion'],
        init_script=rtconfig['init-script'],
        env_script=rtconfig['env-script'],
        err_script=rtconfig['err-script'],
        exit_script=rtconfig['exit-script'],
        pre_script=rtconfig['pre-script'],
        post_script=rtconfig['post-script'],
        work_sub_dir=rtconfig['work sub-directory'],
        execution_time_limit=str(rtconfig['execution time limit'] or ''),
        execution_polling_intervals=listjoin(
            rtconfig['execution polling intervals']
        ),
        execution_retry_delays=listjoin(
            rtconfig['execution retry delays']
        ),
        submission_polling_intervals=listjoin(
            rtconfig['submission polling intervals']
        ),
        submission_retry_delays=listjoin(
            rtconfig['submission retry delays']
        ),
        directives=json.dumps(
            [
                {'key': key, 'value': value}
                for key, value in directives.items()
            ]
        ),
        environment=json.dumps(
            [
                {'key': key, 'value': value}
                for key, value in environment.items()
            ]
        ),
        outputs=json.dumps(
            [
                {'key': key, 'value': value}
                for key, value in outputs.items()
            ]
        )
    )


def apply_delta(key, delta, data):
    """Apply delta to specific data-store workflow and type."""
    # Assimilate new data
    if getattr(delta, 'added', False):
        if key != WORKFLOW:
            data[key].update({e.id: e for e in delta.added})
        elif delta.added.ListFields():
            data[key].CopyFrom(delta.added)
    # Merge in updated fields
    if getattr(delta, 'updated', False):
        if key == WORKFLOW:
            # Clear fields that require overwrite with delta
            field_set = {f.name for f, _ in delta.updated.ListFields()}
            for field in CLEAR_FIELD_MAP[key]:
                if field in field_set or delta.updated.states_updated:
                    data[key].ClearField(field)
            data[key].MergeFrom(delta.updated)
        else:
            for element in delta.updated:
                try:
                    data_element = data[key][element.id]
                    # Clear fields that require overwrite with delta
                    if CLEAR_FIELD_MAP[key]:
                        for field, _ in element.ListFields():
                            if field.name in CLEAR_FIELD_MAP[key]:
                                data_element.ClearField(field.name)
                    data_element.MergeFrom(element)
                except KeyError as exc:
                    # Ensure data-sync doesn't fail with
                    # network issues, sync reconcile/validate will catch.
                    LOG.debug(
                        'Missing Data-Store element '
                        'on update application: %s' % str(exc)
                    )
                    continue
    # Prune data elements
    if hasattr(delta, 'pruned'):
        # UIS flag to prune workflow, set externally.
        if key == WORKFLOW:
            if delta.HasField('pruned'):
                data[WORKFLOW].pruned = True
            return
        # Prune data elements by id
        for del_id in delta.pruned:
            if del_id not in data[key]:
                continue
            # Remove relationships.
            # The suppression of key/value errors is to avoid
            # elements and their relationships missing on reload.
            if key == TASK_PROXIES:
                # remove relationship from task
                with suppress(KeyError, ValueError):
                    data[TASKS][data[key][del_id].task].proxies.remove(del_id)
                # remove relationship from parent/family
                with suppress(KeyError, ValueError):
                    data[FAMILY_PROXIES][
                        data[key][del_id].first_parent
                    ].child_tasks.remove(del_id)
                # remove relationship from workflow
                with suppress(KeyError, ValueError):
                    getattr(data[WORKFLOW], key).remove(del_id)
            elif key == FAMILY_PROXIES:
                with suppress(KeyError, ValueError):
                    data[FAMILIES][
                        data[key][del_id].family
                    ].proxies.remove(del_id)
                with suppress(KeyError, ValueError):
                    data[FAMILY_PROXIES][
                        data[key][del_id].first_parent
                    ].child_families.remove(del_id)
                with suppress(KeyError, ValueError):
                    getattr(data[WORKFLOW], key).remove(del_id)
            elif key == EDGES:
                edge = data[key][del_id]
                with suppress(KeyError, ValueError):
                    data[TASK_PROXIES][edge.source].edges.remove(del_id)
                with suppress(KeyError, ValueError):
                    data[TASK_PROXIES][edge.target].edges.remove(del_id)
                with suppress(KeyError, ValueError):
                    getattr(data[WORKFLOW], key).edges.remove(del_id)
            elif key == JOBS:
                # Jobs are only removed if their task is, so only need
                # to remove relationship from workflow.
                with suppress(KeyError, ValueError):
                    getattr(data[WORKFLOW], key).remove(del_id)
            # remove/prune element from data-store
            del data[key][del_id]


def create_delta_store(delta=None, workflow_id=None):
    """Create a mini data-store out of the all deltas message.

    Args:
        delta (cylc.flow.data_messages_pb2.AllDeltas):
            The message of accumulated deltas for publish/push.
        workflow_id (str):
            The workflow ID.

    Returns:
        dict

    """
    if not isinstance(delta, AllDeltas):
        delta = AllDeltas()
    delta_store = {
        DELTA_ADDED: deepcopy(DATA_TEMPLATE),
        DELTA_UPDATED: deepcopy(DATA_TEMPLATE),
        DELTA_PRUNED: {
            key: []
            for key in DATA_TEMPLATE.keys()
            if key is not WORKFLOW
        },
    }
    if workflow_id is not None:
        delta_store['id'] = workflow_id
    # ListFields returns a list fields that have been set (not all).
    for field, value in delta.ListFields():
        for sub_field, sub_value in value.ListFields():
            if sub_field.name in delta_store:
                if (
                        field.name == WORKFLOW
                        or sub_field.name == DELTA_PRUNED
                ):
                    field_data = sub_value
                else:
                    field_data = {
                        s.id: s
                        for s in sub_value
                    }
                delta_store[sub_field.name][field.name] = field_data
    return delta_store


class DataStoreMgr:
    """Manage the workflow data store.

    Attributes:
        .ancestors (dict):
            Local store of config.get_first_parent_ancestors()
        .data (dict):
            .edges (dict):
                cylc.flow.data_messages_pb2.PbEdge by internal ID.
            .families (dict):
                cylc.flow.data_messages_pb2.PbFamily by name (internal ID).
            .family_proxies (dict):
                cylc.flow.data_messages_pb2.PbFamilyProxy by internal ID.
            .jobs (dict):
                cylc.flow.data_messages_pb2.PbJob by internal ID.
            .tasks (dict):
                cylc.flow.data_messages_pb2.PbTask by name (internal ID).
            .task_proxies (dict):
                cylc.flow.data_messages_pb2.PbTaskProxy by internal ID.
            .workflow (cylc.flow.data_messages_pb2.PbWorkflow)
                Message containing the global information of the workflow.
        .descendants (dict):
            Local store of config.get_first_parent_descendants()
        .n_edge_distance (int):
            Maximum distance of the data-store graph from the active pool.
        .parents (dict):
            Local store of config.get_parent_lists()
        .publish_deltas (list):
            Collection of the latest applied deltas for publishing.
        .schd (cylc.flow.scheduler.Scheduler):
            Workflow scheduler object.
        .workflow_id (str):
            ID of the workflow service containing owner and name.

    Arguments:
        schd (cylc.flow.scheduler.Scheduler):
            Workflow scheduler instance.
    """

    ERR_PREFIX_JOBID_MATCH = 'No matching jobs found: '
    ERR_PREFIX_JOB_NOT_ON_SEQUENCE = 'Invalid cycle point for job: '

    def __init__(self, schd, n_edge_distance=1):
        self.schd = schd
        self.id_ = Tokens(
            user=self.schd.owner,
            workflow=self.schd.workflow,
        )  # TODO: rename and move to scheduler
        self.workflow_id = self.id_.workflow_id
        self.ancestors = {}
        self.descendants = {}
        self.parents = {}
        self.state_update_families = set()
        self.updated_state_families = set()
        # Update workflow state totals once more post delta application.
        self.state_update_follow_on = False
        self.n_edge_distance = n_edge_distance
        self.next_n_edge_distance = None
        self.latest_state_tasks = {
            state: deque(maxlen=LATEST_STATE_TASKS_QUEUE_SIZE)
            for state in TASK_STATUSES_ORDERED
        }
        self.xtrigger_tasks: Dict[str, Set[Tuple[str, str]]] = {}
        # Managed data types
        self.data = {
            self.workflow_id: deepcopy(DATA_TEMPLATE)
        }
        self.added = deepcopy(DATA_TEMPLATE)
        self.updated = deepcopy(DATA_TEMPLATE)
        self.deltas = {
            EDGES: EDeltas(),
            FAMILIES: FDeltas(),
            FAMILY_PROXIES: FPDeltas(),
            JOBS: JDeltas(),
            TASKS: TDeltas(),
            TASK_PROXIES: TPDeltas(),
            WORKFLOW: WDeltas(),
        }
        # internal delta
        self.delta_queues = {self.workflow_id: {}}
        self.publish_deltas = []
        # internal n-window
        self.all_task_pool = set()
        self.all_n_window_nodes = set()
        self.n_window_nodes = {}
        self.n_window_edges = set()
        self.n_window_node_walks = {}
        self.n_window_completed_walks = set()
        self.n_window_depths = {}
        self.update_window_depths = False
        self.db_load_task_proxies = {}
        self.family_pruned_ids = set()
        self.prune_trigger_nodes = {}
        self.prune_flagged_nodes = set()
        self.pruned_task_proxies = set()
        self.updates_pending = False
        self.updates_pending_follow_on = False
        self.publish_pending = False

    def initiate_data_model(self, reloaded=False):
        """Initiate or Update data model on start/restart/reload.

        Args:
            reloaded (bool, optional):
                Reset data-store before regenerating.

        """
        # Reset attributes/data-store on reload:
        if reloaded:
            self.__init__(self.schd, self.n_edge_distance)

        # Static elements
        self.generate_definition_elements()

        # Update workflow statuses and totals (assume needed)
        self.update_workflow(True)

        # Apply current deltas
        self.batch_deltas()
        self.apply_delta_batch()
        # Clear deltas after application
        self.clear_delta_store()
        self.clear_delta_batch()

        # Gather the store as batch of deltas for publishing
        self.batch_deltas(True)
        self.apply_delta_checksum()
        self.publish_deltas = self.get_publish_deltas()

        self.updates_pending = False

        # Clear second batch after publishing
        self.clear_delta_batch()

    def generate_definition_elements(self):
        """Generate static definition data elements.

        Populates the tasks, families, and workflow elements
        with data from and/or derived from the workflow definition.

        """
        config = self.schd.config
        update_time = time()
        tasks = self.added[TASKS]
        families = self.added[FAMILIES]
        workflow = self.added[WORKFLOW]
        workflow.id = self.workflow_id
        workflow.n_edge_distance = self.n_edge_distance
        workflow.last_updated = update_time
        workflow.stamp = f'{workflow.id}@{workflow.last_updated}'
        # Treat play/restart as hard reload of definition.
        workflow.reloaded = True

        graph = workflow.edges
        graph.leaves[:] = config.leaves
        graph.feet[:] = config.feet
        for key, info in config.workflow_polling_tasks.items():
            graph.workflow_polling_tasks.add(
                local_proxy=key,
                workflow=info[0],
                remote_proxy=info[1],
                req_state=info[2],
                graph_string=info[3],
            )

        ancestors = config.get_first_parent_ancestors()
        descendants = config.get_first_parent_descendants()
        parents = config.get_parent_lists()

        # Create definition elements for graphed tasks.
        for name, tdef in config.taskdefs.items():
            t_id = self.definition_id(name)
            t_stamp = f'{t_id}@{update_time}'
            task = PbTask(
                stamp=t_stamp,
                id=t_id,
                name=name,
                depth=len(ancestors[name]) - 1,
            )
            task.namespace[:] = tdef.namespace_hierarchy
            task.first_parent = self.definition_id(ancestors[name][1])
            user_defined_meta = {}
            for key, val in dict(tdef.describe()).items():
                if key in ['title', 'description', 'URL']:
                    setbuff(task.meta, key, val)
                else:
                    user_defined_meta[key] = val
            task.meta.user_defined = json.dumps(user_defined_meta)
            elapsed_time = task_mean_elapsed_time(tdef)
            if elapsed_time:
                task.mean_elapsed_time = elapsed_time
            task.parents.extend([
                self.definition_id(p_name)
                for p_name in parents[name]
            ])
            task.runtime.CopyFrom(runtime_from_config(tdef.rtconfig))
            tasks[t_id] = task

        # Created family definition elements for first parent
        # ancestors of graphed tasks.
        for key, names in ancestors.items():
            for name in names:
                if (
                        key == name or
                        name in families
                ):
                    continue
                f_id = self.definition_id(name)
                f_stamp = f'{f_id}@{update_time}'
                family = PbFamily(
                    stamp=f_stamp,
                    id=f_id,
                    name=name,
                    depth=len(ancestors[name]) - 1,
                )
                famcfg = config.cfg['runtime'][name]
                user_defined_meta = {}
                for key, val in famcfg.get('meta', {}).items():
                    if key in ['title', 'description', 'URL']:
                        setbuff(family.meta, key, val)
                    else:
                        user_defined_meta[key] = val
                family.meta.user_defined = json.dumps(user_defined_meta)
                family.parents.extend(
                    self.definition_id(p_name)
                    for p_name in parents[name]
                )
                with suppress(IndexError):
                    family.first_parent = (
                        self.definition_id(ancestors[name][1])
                    )
                family.runtime.CopyFrom(runtime_from_config(famcfg))
                families[f_id] = family

        for name, parent_list in parents.items():
            if not parent_list:
                continue
            fam = parent_list[0]
            f_id = self.definition_id(fam)
            if f_id in families:
                ch_id = self.definition_id(name)
                if name in config.taskdefs:
                    families[f_id].child_tasks.append(ch_id)
                else:
                    families[f_id].child_families.append(ch_id)

        # Populate static fields of workflow
        workflow.api_version = API
        workflow.cylc_version = CYLC_VERSION
        workflow.name = self.schd.workflow
        workflow.owner = self.schd.owner
        workflow.host = self.schd.host
        workflow.port = self.schd.server.port or -1
        workflow.pub_port = self.schd.server.pub_port or -1
        user_defined_meta = {}
        for key, val in config.cfg['meta'].items():
            if key in ['title', 'description', 'URL']:
                setbuff(workflow.meta, key, val)
            else:
                user_defined_meta[key] = val
        workflow.meta.user_defined = json.dumps(user_defined_meta)
        workflow.tree_depth = max([
            len(val)
            for val in config.get_first_parent_ancestors(pruned=True).values()
        ]) - 1

        if get_utc_mode():
            time_zone_info = TIME_ZONE_UTC_INFO
        else:
            time_zone_info = TIME_ZONE_LOCAL_INFO
        for key, val in time_zone_info.items():
            setbuff(workflow.time_zone_info, key, val)

        workflow.run_mode = config.run_mode()
        workflow.cycling_mode = config.cfg['scheduling']['cycling mode']
        workflow.workflow_log_dir = self.schd.workflow_log_dir
        workflow.job_log_names.extend(list(JOB_LOG_OPTS.values()))
        workflow.ns_def_order.extend(config.ns_defn_order)

        workflow.broadcasts = json.dumps(self.schd.broadcast_mgr.broadcasts)

        workflow.tasks.extend(list(tasks))
        workflow.families.extend(list(families))

        self.ancestors = ancestors
        self.descendants = descendants
        self.parents = parents

    def increment_graph_window(
        self,
        source_tokens: Tokens,
        point: 'PointBase',
        flow_nums: 'FlowNums',
        is_manual_submit: bool = False,
        itask: Optional['TaskProxy'] = None
    ) -> None:
        """Generate graph window about active task proxy to n-edge-distance.

        Fills in graph walk from existing walks if possible, otherwise expands
        the graph front from whereever hasn't been walked.
        Walk nodes are grouped into locations which are tag according to
        parent child path, i.e. 'cpc' would be children-parents-children away
        from active/start task. Which not only provide a way to cheaply rewalk,
        but also the edge distance from origin.
        The futherest child boundary nodes are registered as prune triggers for
        the origin's parents, so when they become active the parents are
        assessed for pruning eligibility.

        Args:
            source_tokens
            point
            flow_nums
            is_manual_submit
            itask:
                Active/Other task proxy, passed in with pool invocation.
        """

        # common refrences
        active_id = source_tokens.id
        all_walks = self.n_window_node_walks
        taskdefs = self.schd.config.taskdefs
        final_point = self.schd.config.final_point

        # walk keys/tags
        # Children location tag
        c_tag = 'c'
        # Parents location tag
        p_tag = 'p'

        # Setup walk fields:
        # - locations (locs): i.e. 'cpc' children-parents-children from origin,
        #   with their respective node ids.
        # - orphans: task no longer exists in workflow.
        # - done_locs: set of locactions that have been walked over.
        # - done_ids: set of node ids that have been walked (from initial
        #   walk filling, that may not have been the entire walk).
        # If walk already completed, must have gone from non-active to active
        # again.. So redo walk (as walk nodes may be pruned).
        if (
            active_id not in all_walks
            or active_id in self.n_window_completed_walks
        ):
            all_walks[active_id] = {
                'locations': {},
                'orphans': set(),
                'done_locs': set(),
                'done_ids': set(),
                'walk_ids': {active_id},
                'depths': {
                    depth: set()
                    for depth in range(1, self.n_edge_distance + 1)
                }
            }
            if active_id in self.n_window_completed_walks:
                self.n_window_completed_walks.remove(active_id)
        active_walk = all_walks[active_id]
        active_locs = active_walk['locations']
        if source_tokens['task'] not in taskdefs:
            active_walk['orphans'].add(active_id)

        # Generate task proxy node
        self.n_window_nodes[active_id] = set()

        self.generate_ghost_task(
            source_tokens,
            point,
            flow_nums,
            is_parent=False,
            itask=itask,
            replace_existing=True,
        )

        # Pre-populate from previous walks
        # Will check all location permutations.
        # There may be short cuts for parent locs, however children will more
        # likely be incomplete walks with no 'done_locs' and using parent's
        # children will required sifting out cousin branches.
        working_locs: List[str] = []
        if self.n_edge_distance > 1:
            if c_tag in active_locs:
                working_locs.extend(('cc', 'cp'))
            if p_tag in active_locs:
                working_locs.extend(('pp', 'pc'))
            n_depth = 2
        while working_locs:
            for w_loc in working_locs:
                loc_done = True
                # Most will be incomplete walks, however, we can check.
                # i.e. parents of children may all exist.
                if w_loc[:-1] in active_locs:
                    for loc_id in active_locs[w_loc[:-1]]:
                        if loc_id not in all_walks:
                            loc_done = False
                            break
                else:
                    continue
                # find child nodes of parent location,
                # i.e. 'cpcc' = 'cpc' + 'c'
                w_set = set().union(*(
                    all_walks[loc_id]['locations'][w_loc[-1]]
                    for loc_id in active_locs[w_loc[:-1]]
                    if (
                        loc_id in all_walks
                        and w_loc[-1] in all_walks[loc_id]['locations']
                    )
                ))
                w_set.difference_update(active_walk['walk_ids'])
                if w_set:
                    active_locs[w_loc] = w_set
                    active_walk['walk_ids'].update(w_set)
                    active_walk['depths'][n_depth].update(w_set)
                    # If child/parent nodes have been pruned we will need
                    # to regenerate them.
                    if (
                        loc_done
                        and not w_set.difference(self.all_n_window_nodes)
                    ):
                        active_walk['done_locs'].add(w_loc[:-1])
                        active_walk['done_ids'].update(
                            active_locs[w_loc[:-1]]
                        )
            working_locs = [
                new_loc
                for loc in working_locs
                if loc in active_locs and len(loc) < self.n_edge_distance
                for new_loc in (loc + c_tag, loc + p_tag)
            ]
            n_depth += 1

        # Graph walk
        node_tokens: Tokens
        child_tokens: Tokens
        parent_tokens: Tokens
        walk_incomplete = True
        while walk_incomplete:
            walk_incomplete = False
            # Only walk locations not fully explored
            locations = [
                loc
                for loc in active_locs
                if (

                    len(loc) < self.n_edge_distance
                    and loc not in active_walk['done_locs']
                )
            ]
            # Origin/Active usually first or isolate nodes
            if (
                not active_walk['done_ids']
                and not locations
                and active_id not in active_walk['orphans']
                and self.n_edge_distance != 0
            ):
                locations = ['']
            # Explore/walk locations
            for location in locations:
                walk_incomplete = True
                if not location:
                    loc_nodes = {active_id}
                else:
                    loc_nodes = active_locs[location]
                    active_walk['done_locs'].add(location)
                c_loc = location + c_tag
                p_loc = location + p_tag
                c_ids = set()
                p_ids = set()
                n_depth = len(location) + 1
                # Exclude walked nodes at this location.
                # This also helps avoid walking in a circle.
                for node_id in loc_nodes.difference(active_walk['done_ids']):
                    active_walk['done_ids'].add(node_id)
                    node_tokens = Tokens(node_id)
                    # Don't expand window about orphan task.
                    try:
                        tdef = taskdefs[node_tokens['task']]
                    except KeyError:
                        active_walk['orphans'].add(node_id)
                        continue
                    # Use existing children/parents from other walks.
                    # (note: nodes/edges should already be generated)
                    c_done = False
                    p_done = False
                    if node_id in all_walks and node_id is not active_id:
                        with suppress(KeyError):
                            # If children have been pruned, don't skip,
                            # re-generate them (uncommon or impossible?).
                            if not all_walks[node_id]['locations'][
                                c_tag
                            ].difference(self.all_n_window_nodes):
                                c_ids.update(
                                    all_walks[node_id]['locations'][c_tag]
                                )
                                c_done = True
                        with suppress(KeyError):
                            # If parent have been pruned, don't skip,
                            # re-generate them (more common case).
                            if not all_walks[node_id]['locations'][
                                p_tag
                            ].difference(self.all_n_window_nodes):
                                p_ids.update(
                                    all_walks[node_id]['locations'][p_tag]
                                )
                                p_done = True
                        if p_done and c_done:
                            continue

                    # Children/downstream nodes
                    # TODO: xtrigger is workflow_state edges too
                    # see: https://github.com/cylc/cylc-flow/issues/4582
                    # Reference set for workflow relations
                    nc_ids = set()
                    if not c_done:
                        if itask is not None and n_depth == 1:
                            graph_children = itask.graph_children
                        else:
                            graph_children = generate_graph_children(
                                tdef,
                                get_point(node_tokens['cycle'])
                            )
                        for items in graph_children.values():
                            for child_name, child_point, _ in items:
                                if child_point > final_point:
                                    continue
                                child_tokens = self.id_.duplicate(
                                    cycle=str(child_point),
                                    task=child_name,
                                )
                                self.generate_ghost_task(
                                    child_tokens,
                                    child_point,
                                    flow_nums,
                                    False,
                                    None,
                                    n_depth
                                )
                                self.generate_edge(
                                    node_tokens,
                                    child_tokens,
                                    active_id
                                )
                                nc_ids.add(child_tokens.id)

                    # Parents/upstream nodes
                    np_ids = set()
                    if not p_done:
                        for items in generate_graph_parents(
                            tdef,
                            get_point(node_tokens['cycle']),
                            taskdefs
                        ).values():
                            for parent_name, parent_point, _ in items:
                                if parent_point > final_point:
                                    continue
                                parent_tokens = self.id_.duplicate(
                                    cycle=str(parent_point),
                                    task=parent_name,
                                )
                                self.generate_ghost_task(
                                    parent_tokens,
                                    parent_point,
                                    flow_nums,
                                    True,
                                    None,
                                    n_depth
                                )
                                # reverse for parent
                                self.generate_edge(
                                    parent_tokens,
                                    node_tokens,
                                    active_id
                                )
                                np_ids.add(parent_tokens.id)

                    # Register new walk
                    if node_id not in all_walks:
                        all_walks[node_id] = {
                            'locations': {},
                            'done_ids': set(),
                            'done_locs': set(),
                            'orphans': set(),
                            'walk_ids': {node_id} | nc_ids | np_ids,
                            'depths': {
                                depth: set()
                                for depth in range(1, self.n_edge_distance + 1)
                            }
                        }
                    if nc_ids:
                        all_walks[node_id]['locations'][c_tag] = nc_ids
                        all_walks[node_id]['depths'][1].update(nc_ids)
                        c_ids.update(nc_ids)
                    if np_ids:
                        all_walks[node_id]['locations'][p_tag] = np_ids
                        all_walks[node_id]['depths'][1].update(np_ids)
                        p_ids.update(np_ids)

                # Create location association
                c_ids.difference_update(active_walk['walk_ids'])
                if c_ids:
                    active_locs.setdefault(c_loc, set()).update(c_ids)
                p_ids.difference_update(active_walk['walk_ids'])
                if p_ids:
                    active_locs.setdefault(p_loc, set()).update(p_ids)
                active_walk['walk_ids'].update(c_ids, p_ids)
                active_walk['depths'][n_depth].update(c_ids, p_ids)

        self.n_window_completed_walks.add(active_id)
        self.n_window_nodes[active_id].update(active_walk['walk_ids'])

        # This part is vital to constructing a set of boundary nodes
        # associated with the n=0 window of current active node.
        # Only trigger pruning for furthest set of boundary nodes
        boundary_nodes: Set[str] = set()
        max_level: int = 0
        with suppress(ValueError):
            max_level = max(
                len(loc)
                for loc in active_locs
                if p_tag not in loc
            )
            # add the most distant child as a trigger to prune it.
            boundary_nodes.update(*(
                active_locs[loc]
                for loc in active_locs
                if p_tag not in loc and len(loc) >= max_level
            ))
        if not boundary_nodes and not max_level:
            # Could be self-reference node foo:failed => foo
            boundary_nodes = {active_id}
        # associate
        for tp_id in boundary_nodes:
            try:
                self.prune_trigger_nodes.setdefault(tp_id, set()).update(
                    active_walk['walk_ids']
                )
                self.prune_trigger_nodes[tp_id].discard(tp_id)
            except KeyError:
                self.prune_trigger_nodes.setdefault(tp_id, set()).add(
                    active_id
                )
        # flag manual triggers for pruning on deletion.
        if is_manual_submit:
            self.prune_trigger_nodes.setdefault(active_id, set()).add(
                active_id
            )
        if active_walk['orphans']:
            self.prune_trigger_nodes.setdefault(active_id, set()).union(
                active_walk['orphans']
            )
        # Check if active node is another's boundary node
        # to flag its paths for pruning.
        if active_id in self.prune_trigger_nodes:
            self.prune_flagged_nodes.update(
                self.prune_trigger_nodes[active_id])
            del self.prune_trigger_nodes[active_id]

    def generate_edge(
        self,
        parent_tokens: Tokens,
        child_tokens: Tokens,
        active_id: str,
    ) -> None:
        """Construct edge of child and parent task proxy node."""
        # Initiate edge element.
        e_id = self.edge_id(parent_tokens, child_tokens)
        if e_id in self.n_window_edges:
            return
        if (
            e_id not in self.data[self.workflow_id][EDGES]
            and e_id not in self.added[EDGES]
        ):
            self.added[EDGES][e_id] = PbEdge(
                id=e_id,
                source=parent_tokens.id,
                target=child_tokens.id
            )
            # Add edge id to node field for resolver reference
            self.updated[TASK_PROXIES].setdefault(
                child_tokens.id,
                PbTaskProxy(id=child_tokens.id)).edges.append(e_id)
            self.updated[TASK_PROXIES].setdefault(
                parent_tokens.id,
                PbTaskProxy(id=parent_tokens.id)).edges.append(e_id)
            getattr(self.updated[WORKFLOW], EDGES).edges.append(e_id)
            self.n_window_edges.add(e_id)

    def remove_pool_node(self, name, point):
        """Remove ID reference and flag isolate node/branch for pruning."""
        tp_id = self.id_.duplicate(
            cycle=str(point),
            task=name,
        ).id
        if tp_id in self.all_task_pool:
            self.all_task_pool.remove(tp_id)
            self.updates_pending = True
        # flagged isolates/end-of-branch nodes for pruning on removal
        if (
                tp_id in self.prune_trigger_nodes and
                tp_id in self.prune_trigger_nodes[tp_id]
        ):
            self.prune_flagged_nodes.update(self.prune_trigger_nodes[tp_id])
            del self.prune_trigger_nodes[tp_id]
        elif (
                tp_id in self.n_window_nodes and
                self.n_window_nodes[tp_id].isdisjoint(self.all_task_pool)
        ):
            self.prune_flagged_nodes.add(tp_id)
        elif tp_id in self.n_window_node_walks:
            self.prune_flagged_nodes.update(
                self.n_window_node_walks[tp_id]['walk_ids']
            )
        self.updates_pending = True

    def add_pool_node(self, name, point):
        """Add external ID reference for internal task pool node."""
        tp_id = self.id_.duplicate(
            cycle=str(point),
            task=name,
        ).id
        self.all_task_pool.add(tp_id)
        self.update_window_depths = True

    def generate_ghost_task(
        self,
        tokens: Tokens,
        point: 'PointBase',
        flow_nums: 'FlowNums',
        is_parent: bool = False,
        itask: Optional['TaskProxy'] = None,
        n_depth: int = 0,
        replace_existing: bool = False,
    ) -> None:
        """Create task-point element populated with static data.

        Args:
            source_tokens
            point
            flow_nums
            is_parent: Used to determine whether to load DB state.
            itask: Update task-node from corresponding task proxy object.
            n_depth: n-window graph edge distance.
            replace_existing: Replace any existing data for task as it may
                be out of date (e.g. flow nums).
        """
        tp_id = tokens.id
        if (
            tp_id in self.data[self.workflow_id][TASK_PROXIES]
            or tp_id in self.added[TASK_PROXIES]
        ):
            if replace_existing and itask is not None:
                self.delta_from_task_proxy(itask)
            return

        name = tokens['task']
        point_string = tokens['cycle']
        t_id = self.definition_id(name)

        if itask is None:
            itask = self.schd.pool.get_task(point_string, name)

        if itask is None:
            itask = TaskProxy(
                self.id_,
                self.schd.config.get_taskdef(name),
                point,
                flow_nums,
                submit_num=0,
                data_mode=True,
                sequential_xtrigger_labels=(
                    self.schd.xtrigger_mgr.xtriggers.sequential_xtrigger_labels
                ),
            )

        is_orphan = False
        if name not in self.schd.config.taskdefs:
            is_orphan = True
            self.generate_orphan_task(itask)

        # Most of the time the definition node will be in the store.
        try:
            task_def = self.data[self.workflow_id][TASKS][t_id]
        except KeyError:
            try:
                task_def = self.added[TASKS][t_id]
            except KeyError:
                # Task removed from workflow definition.
                return

        update_time = time()
        tp_stamp = f'{tp_id}@{update_time}'
        tproxy = PbTaskProxy(
            stamp=tp_stamp,
            id=tp_id,
            task=t_id,
            cycle_point=point_string,
            is_held=(
                (name, point)
                in self.schd.pool.tasks_to_hold
            ),
            depth=task_def.depth,
            graph_depth=n_depth,
            name=name,
        )
        self.all_n_window_nodes.add(tp_id)
        self.n_window_depths.setdefault(n_depth, set()).add(tp_id)

        tproxy.namespace[:] = task_def.namespace
        if is_orphan:
            tproxy.ancestors[:] = [
                self.id_.duplicate(
                    cycle=point_string,
                    task='root',
                ).id
            ]
        else:
            tproxy.ancestors[:] = [
                self.id_.duplicate(
                    cycle=point_string,
                    task=a_name,
                ).id
                for a_name in self.ancestors[task_def.name]
                if a_name != task_def.name
            ]
        tproxy.first_parent = tproxy.ancestors[0]

        self.added[TASK_PROXIES][tp_id] = tproxy
        getattr(self.updated[WORKFLOW], TASK_PROXIES).append(tp_id)
        self.updated[TASKS].setdefault(
            t_id,
            PbTask(
                stamp=f'{t_id}@{update_time}',
                id=t_id,
            )
        ).proxies.append(tp_id)
        self.generate_ghost_family(tproxy.first_parent, child_task=tp_id)
        self.state_update_families.add(tproxy.first_parent)

        # Active, but not in the data-store yet (new).
        if tp_id in self.n_window_nodes:
            self._process_internal_task_proxy(itask, tproxy)
            # Has run before, so get history.
            # Cannot batch as task is active (all jobs retrieved at once).
            if itask.submit_num > 0:
                flow_db = self.schd.workflow_db_mgr.pri_dao
                for row in flow_db.select_jobs_for_datastore(
                        {itask.identity}
                ):
                    self.insert_db_job(1, row)
        else:
            # Batch non-active node for load of DB history.
            self.db_load_task_proxies[itask.identity] = (
                itask,
                is_parent,
            )

        self.updates_pending = True

        return

    def generate_orphan_task(self, itask):
        """Generate orphan task definition."""
        update_time = time()
        tdef = itask.tdef
        name = tdef.name
        t_id = self.definition_id(name)
        t_stamp = f'{t_id}@{update_time}'
        task = PbTask(
            stamp=t_stamp,
            id=t_id,
            name=name,
            depth=1,
        )
        task.namespace[:] = tdef.namespace_hierarchy
        task.first_parent = self.definition_id('root')
        user_defined_meta = {}
        for key, val in dict(tdef.describe()).items():
            if key in ['title', 'description', 'URL']:
                setbuff(task.meta, key, val)
            else:
                user_defined_meta[key] = val
        task.meta.user_defined = json.dumps(user_defined_meta)
        elapsed_time = task_mean_elapsed_time(tdef)
        if elapsed_time:
            task.mean_elapsed_time = elapsed_time
        task.parents[:] = [task.first_parent]

        task.runtime.CopyFrom(runtime_from_config(tdef.rtconfig))

        self.added[TASKS][t_id] = task

    def generate_ghost_family(self, fp_id, child_fam=None, child_task=None):
        """Generate the family-point elements from given ID if non-existent.

        Adds the ID of the child proxy that called for it's creation. Also
        generates parents recursively to root if they don't exist.

        Args:
            fp_id (str):
                Family proxy ID
            child_fam (str):
                Family proxy ID
            child_task (str):
                Task proxy ID

        Returns:

            None

        """

        update_time = time()
        families = self.data[self.workflow_id][FAMILIES]
        if not families:
            families = self.added[FAMILIES]
        fp_data = self.data[self.workflow_id][FAMILY_PROXIES]
        fp_added = self.added[FAMILY_PROXIES]
        fp_updated = self.updated[FAMILY_PROXIES]
        if fp_id in fp_data:
            fp_delta = fp_data[fp_id]
            fp_parent = fp_updated.setdefault(fp_id, PbFamilyProxy(id=fp_id))
        elif fp_id in fp_added:
            fp_delta = fp_added[fp_id]
            fp_parent = fp_added.setdefault(fp_id, PbFamilyProxy(id=fp_id))
        else:
            tokens = Tokens(fp_id)
            point_string = tokens['cycle']
            name = tokens['task']
            fam = families[self.definition_id(name)]
            fp_delta = PbFamilyProxy(
                stamp=f'{fp_id}@{update_time}',
                id=fp_id,
                cycle_point=point_string,
                name=fam.name,
                family=fam.id,
                depth=fam.depth,
            )
            fp_delta.ancestors[:] = [
                self.id_.duplicate(
                    cycle=point_string,
                    task=a_name,
                ).id
                for a_name in self.ancestors[fam.name]
                if a_name != fam.name
            ]
            if fp_delta.ancestors:
                fp_delta.first_parent = fp_delta.ancestors[0]

            fp_delta.runtime.CopyFrom(
                runtime_from_config(
                    self._apply_broadcasts_to_runtime(
                        tokens,
                        self.schd.config.cfg['runtime'][fam.name]
                    )
                )
            )

            self.added[FAMILY_PROXIES][fp_id] = fp_delta
            fp_parent = fp_delta
            # Add ref ID to family element
            f_delta = PbFamily(id=fam.id, stamp=f'{fam.id}@{update_time}')
            f_delta.proxies.append(fp_id)
            self.updated[FAMILIES].setdefault(
                fam.id, PbFamily(id=fam.id)).MergeFrom(f_delta)
            # Add ref ID to workflow element
            getattr(self.updated[WORKFLOW], FAMILY_PROXIES).append(fp_id)
            # Generate this families parent if it not root.
            if fp_delta.first_parent:
                self.generate_ghost_family(
                    fp_delta.first_parent, child_fam=fp_id)
        if child_fam is None:
            fp_parent.child_tasks.append(child_task)
        elif child_fam not in fp_parent.child_families:
            fp_parent.child_families.append(child_fam)

    def apply_task_proxy_db_history(self):
        """Extract and apply DB history on given task proxies."""
        if not self.db_load_task_proxies:
            return

        flow_db = self.schd.workflow_db_mgr.pri_dao

        task_ids = set(self.db_load_task_proxies.keys())
        # Batch load rows with matching cycle & name column pairs.
        prereq_ids = set()
        for (
                cycle, name, flow_nums_str, status, submit_num, outputs_str
        ) in flow_db.select_tasks_for_datastore(task_ids):
            tokens = self.id_.duplicate(
                cycle=cycle,
                task=name,
            )
            relative_id = tokens.relative_id
            itask, is_parent = self.db_load_task_proxies[relative_id]
            itask.submit_num = submit_num
            flow_nums = deserialise_set(flow_nums_str)
            # Do not set states and outputs for future tasks in flow.
            if (
                    itask.flow_nums and
                    flow_nums != itask.flow_nums and
                    not is_parent
            ):
                itask.state_reset(TASK_STATUS_WAITING, silent=True)
                continue
            else:
                itask.flow_nums = flow_nums
                itask.state_reset(status, silent=True)
            if (
                    outputs_str is not None
                    and itask.state(
                        TASK_STATUS_RUNNING,
                        TASK_STATUS_FAILED,
                        TASK_STATUS_SUCCEEDED
                    )
            ):
                for message in json.loads(outputs_str):
                    itask.state.outputs.set_message_complete(message)
            # Gather tasks with flow id.
            prereq_ids.add(f'{relative_id}/{flow_nums_str}')

        # Batch load prerequisites of tasks according to flow.
        prereqs_map = {}
        for (
                cycle, name, prereq_name,
                prereq_cycle, prereq_output, satisfied
        ) in flow_db.select_prereqs_for_datastore(prereq_ids):
            tokens = self.id_.duplicate(
                cycle=cycle,
                task=name,
            )
            prereqs_map.setdefault(tokens.relative_id, {})[
                (prereq_cycle, prereq_name, prereq_output)
            ] = satisfied if satisfied != '0' else False

        for ikey, prereqs in prereqs_map.items():
            for itask_prereq in (
                    self.db_load_task_proxies[ikey][0].state.prerequisites
            ):
                for key in itask_prereq.satisfied.keys():
                    try:
                        itask_prereq.satisfied[key] = prereqs[key]
                    except KeyError:
                        # This prereq is not in the DB: new dependencies
                        # added to an already-spawned task before restart.
                        itask_prereq.satisfied[key] = False

        # Extract info from itasks to data-store.
        for task_info in self.db_load_task_proxies.values():
            self._process_internal_task_proxy(
                task_info[0],
                self.added[TASK_PROXIES][
                    self.id_.duplicate(task_info[0].tokens).id
                ]
            )

        # Batch load jobs from DB.
        for row in flow_db.select_jobs_for_datastore(task_ids):
            self.insert_db_job(1, row)

        self.db_load_task_proxies.clear()

    def _process_internal_task_proxy(
        self,
        itask: 'TaskProxy',
        tproxy: PbTaskProxy,
    ):
        """Extract information from internal task proxy object."""

        update_time = time()

        tproxy.state = itask.state.status
        tproxy.flow_nums = serialise_set(itask.flow_nums)

        prereq_list = []
        for prereq in itask.state.prerequisites:
            # Protobuf messages populated within
            prereq_obj = prereq.api_dump()
            if prereq_obj:
                prereq_list.append(prereq_obj)
        del tproxy.prerequisites[:]
        tproxy.prerequisites.extend(prereq_list)

        for label, message, satisfied in itask.state.outputs:
            output = tproxy.outputs[label]
            output.label = label
            output.message = message
            output.satisfied = satisfied
            output.time = update_time

        for trig, satisfied in itask.state.external_triggers.items():
            ext_trig = tproxy.external_triggers[trig]
            ext_trig.id = trig
            ext_trig.satisfied = satisfied

        for label, satisfied in itask.state.xtriggers.items():
            sig = self.schd.xtrigger_mgr.get_xtrig_ctx(
                itask, label).get_signature()
            xtrig = tproxy.xtriggers[sig]
            xtrig.id = sig
            xtrig.label = label
            xtrig.satisfied = satisfied
            self.xtrigger_tasks.setdefault(sig, set()).add((tproxy.id, label))

        if tproxy.state in self.latest_state_tasks:
            tp_ref = itask.identity
            tp_queue = self.latest_state_tasks[tproxy.state]
            if tp_ref in tp_queue:
                tp_queue.remove(tp_ref)
            self.latest_state_tasks[tproxy.state].appendleft(tp_ref)

        tproxy.runtime.CopyFrom(
            runtime_from_config(
                self._apply_broadcasts_to_runtime(
                    itask.tokens,
                    itask.tdef.rtconfig
                )
            )
        )

    def _apply_broadcasts_to_runtime(self, tokens, rtconfig):
        # Handle broadcasts
        overrides = self.schd.broadcast_mgr.get_broadcast(tokens)
        if overrides:
            rtconfig = pdeepcopy(rtconfig)
            poverride(rtconfig, overrides, prepend=True)
        return rtconfig

    def insert_job(self, name, cycle_point, status, job_conf):
        """Insert job into data-store.

        Args:
            name (str): Corresponding task name.
            cycle_point (str|PointBase): Cycle point string
            job_conf (dic):
                Dictionary of job configuration used to generate
                the job script.
                (see TaskJobManager._prep_submit_task_job_impl)

        Returns:

            None

        """
        sub_num = job_conf['submit_num']
        tp_tokens = self.id_.duplicate(
            cycle=str(cycle_point),
            task=name,
        )
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(tp_tokens)
        if not tproxy:
            return
        update_time = time()
        j_tokens = tp_tokens.duplicate(job=str(sub_num))
        j_id, job = self.store_node_fetcher(j_tokens)
        if job:
            # Job already exists (i.e. post-submission submit failure)
            return

        if status not in JOB_STATUS_SET:
            return

        j_buf = PbJob(
            stamp=f'{j_id}@{update_time}',
            id=j_id,
            submit_num=sub_num,
            state=status,
            task_proxy=tp_id,
            name=tproxy.name,
            cycle_point=tproxy.cycle_point,
            execution_time_limit=job_conf.get('execution_time_limit'),
            platform=job_conf['platform']['name'],
            job_runner_name=job_conf.get('job_runner_name'),
        )
        # Not all fields are populated with some submit-failures,
        # so use task cfg as base.
        j_cfg = pdeepcopy(self._apply_broadcasts_to_runtime(
            tp_tokens,
            self.schd.config.cfg['runtime'][tproxy.name]
        ))
        for key, val in job_conf.items():
            j_cfg[key] = val
        j_buf.runtime.CopyFrom(runtime_from_config(j_cfg))

        # Add in log files.
        j_buf.job_log_dir = get_task_job_log(
            self.schd.workflow, tproxy.cycle_point, tproxy.name, sub_num)

        self.added[JOBS][j_id] = j_buf
        getattr(self.updated[WORKFLOW], JOBS).append(j_id)
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id,
            PbTaskProxy(
                stamp=f'{tp_id}@{update_time}',
                id=tp_id,
            )
        )
        tp_delta.job_submits = sub_num
        tp_delta.jobs.append(j_id)
        self.updates_pending = True

    def insert_db_job(self, row_idx, row):
        """Load job element from DB post restart."""
        if row_idx == 0:
            LOG.info("LOADING job data")
        (
            point_string,
            name,
            submit_num,
            time_submit,
            submit_status,
            time_run,
            time_run_exit,
            run_status,
            job_runner_name,
            job_id,
            platform_name
        ) = row
        tp_tokens = self.id_.duplicate(
            cycle=point_string,
            task=name,
        )
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(tp_tokens)
        if not tproxy:
            return
        j_tokens = tp_tokens.duplicate(job=str(submit_num))
        j_id = j_tokens.id

        if run_status is not None:
            if run_status == 0:
                status = TASK_STATUS_SUCCEEDED
            else:
                status = TASK_STATUS_FAILED
        elif time_run is not None:
            status = TASK_STATUS_RUNNING
        elif submit_status is not None:
            if submit_status == 0:
                status = TASK_STATUS_SUBMITTED
            else:
                status = TASK_STATUS_SUBMIT_FAILED
        else:
            return

        try:
            update_time = time()
            j_buf = PbJob(
                stamp=f'{j_id}@{update_time}',
                id=j_id,
                submit_num=submit_num,
                state=status,
                task_proxy=tp_id,
                submitted_time=time_submit,
                started_time=time_run,
                finished_time=time_run_exit,
                job_runner_name=job_runner_name,
                job_id=job_id,
                platform=platform_name,
                name=name,
                cycle_point=tproxy.cycle_point,
            )
            # Add in log files.
            j_buf.job_log_dir = get_task_job_log(
                self.schd.workflow, point_string, name, submit_num)
        except WorkflowConfigError:
            LOG.exception((
                'ignoring job %s from the workflow run database\n'
                '(its task definition has probably been deleted).'
            ) % j_id)
        except Exception:
            LOG.exception('could not load job %s' % j_id)
        else:
            self.added[JOBS][j_id] = j_buf
            getattr(self.updated[WORKFLOW], JOBS).append(j_id)
            tp_delta = self.updated[TASK_PROXIES].setdefault(
                tp_id,
                PbTaskProxy(
                    stamp=f'{tp_id}@{update_time}',
                    id=tp_id,
                )
            )
            tp_delta.job_submits = max((submit_num, tp_delta.job_submits))
            tp_delta.jobs.append(j_id)
            self.updates_pending = True

    def update_data_structure(self):
        """Workflow batch updates in the data structure."""

        # Avoids changing window edge distance during edge/node creation
        if self.next_n_edge_distance is not None:
            self.n_edge_distance = self.next_n_edge_distance
            self.window_resize_rewalk()
            self.next_n_edge_distance = None

        # load database history for flagged nodes
        self.apply_task_proxy_db_history()

        self.updates_pending_follow_on = False
        self.prune_data_store()

        # Find depth changes and create deltas
        if self.update_window_depths:
            self.window_depth_finder()

        if self.updates_pending:
            # update
            self.update_family_proxies()

            # Update workflow statuses and totals if needed
            self.update_workflow()

            # Don't process updated deltas of pruned nodes
            self.prune_pruned_updated_nodes()

            # Gather deltas
            self.batch_deltas()
            # Apply all deltas
            self.apply_delta_batch()

        if self.updates_pending:
            self.apply_delta_checksum()
            # Gather this batch of deltas for publish
            self.publish_deltas = self.get_publish_deltas()

        self.updates_pending = self.updates_pending_follow_on

        # Clear deltas
        self.clear_delta_batch()
        self.clear_delta_store()

    def update_workflow_states(self):
        """Batch workflow state updates."""

        # update the workflow state in the data store
        self.update_workflow()

        # push out update deltas
        self.batch_deltas()
        self.apply_delta_batch()
        self.apply_delta_checksum()
        self.publish_deltas = self.get_publish_deltas()

    def window_resize_rewalk(self) -> None:
        """Re-create data-store n-window on resize."""
        # Gather pre-resize window nodes
        if not self.all_n_window_nodes:
            self.all_n_window_nodes = set().union(*(
                v
                for k, v in self.n_window_nodes.items()
                if k in self.all_task_pool
            ))

        # Clear window walks, and walk from scratch.
        self.prune_flagged_nodes.clear()
        self.n_window_node_walks.clear()
        for tp_id in self.all_task_pool:
            tokens = Tokens(tp_id)
            tproxy: PbTaskProxy
            _, tproxy = self.store_node_fetcher(tokens)
            self.increment_graph_window(
                tokens,
                get_point(tokens['cycle']),
                deserialise_set(tproxy.flow_nums)
            )
        # Flag difference between old and new window for pruning.
        self.prune_flagged_nodes.update(
            self.all_n_window_nodes.difference(*(
                v
                for k, v in self.n_window_nodes.items()
                if k in self.all_task_pool
            ))
        )
        self.update_window_depths = True

    def window_depth_finder(self):
        """Recalculate window depths, creating depth deltas."""
        # Setup new window depths
        n_window_depths: Dict[int, Set[str]] = {
            0: self.all_task_pool.copy()
        }

        depth = 1
        # Since starting from smaller depth, exclude those whose depth has
        # already been found.
        depth_found_tasks: Set[str] = self.all_task_pool.copy()
        while depth <= self.n_edge_distance:
            n_window_depths[depth] = set().union(*(
                self.n_window_node_walks[n_id]['depths'][depth]
                for n_id in self.all_task_pool
                if (
                    n_id in self.n_window_node_walks
                    and depth in self.n_window_node_walks[n_id]['depths']
                )
            )).difference(depth_found_tasks)
            depth_found_tasks.update(n_window_depths[depth])
            # Calculate next depth parameters.
            depth += 1

        # Create deltas of those whose depth has changed, a node should only
        # appear once across all depths.
        # So the diff will only contain it at a single depth and if it didn't
        # appear at the same depth previously.
        update_time = time()
        for depth, node_set in n_window_depths.items():
            node_set_diff = node_set.difference(
                self.n_window_depths.setdefault(depth, set())
            )
            if not self.updates_pending and node_set_diff:
                self.updates_pending = True
            for tp_id in node_set_diff:
                tp_delta = self.updated[TASK_PROXIES].setdefault(
                    tp_id, PbTaskProxy(id=tp_id)
                )
                tp_delta.stamp = f'{tp_id}@{update_time}'
                tp_delta.graph_depth = depth
        # Set old to new.
        self.n_window_depths = n_window_depths
        self.update_window_depths = False

    def prune_data_store(self):
        """Remove flagged nodes and edges not in the set of active paths."""

        self.family_pruned_ids.clear()

        if not self.prune_flagged_nodes:
            return

        # Keep all nodes in the path of active tasks.
        self.all_n_window_nodes = set().union(*(
            v
            for k, v in self.n_window_nodes.items()
            if k in self.all_task_pool
        ))
        # Gather all nodes in the paths of tasks flagged for pruning.
        out_paths_nodes = self.prune_flagged_nodes.union(*(
            v
            for k, v in self.n_window_nodes.items()
            if k in self.prune_flagged_nodes
        ))
        # Trim out any nodes in the runahead pool
        out_paths_nodes.difference(self.all_task_pool)
        # Prune only nodes not in the paths of active nodes
        node_ids = out_paths_nodes.difference(self.all_n_window_nodes)
        # Absolute triggers may be present in task pool, so recheck.
        # Clear the rest.
        self.prune_flagged_nodes.intersection_update(self.all_task_pool)

        tp_data = self.data[self.workflow_id][TASK_PROXIES]
        tp_added = self.added[TASK_PROXIES]
        parent_ids = set()
        for tp_id in list(node_ids):
            if tp_id in self.n_window_nodes:
                del self.n_window_nodes[tp_id]
            if tp_id in tp_data:
                node = tp_data[tp_id]
            elif tp_id in tp_added:
                node = tp_added[tp_id]
            else:
                node_ids.remove(tp_id)
                continue
            self.n_window_edges.difference_update(node.edges)
            if tp_id in self.n_window_node_walks:
                del self.n_window_node_walks[tp_id]
            if tp_id in self.n_window_completed_walks:
                self.n_window_completed_walks.remove(tp_id)
            for sig in node.xtriggers:
                self.xtrigger_tasks[sig].remove(
                    (tp_id, node.xtriggers[sig].label)
                )
                if not self.xtrigger_tasks[sig]:
                    del self.xtrigger_tasks[sig]

            self.deltas[TASK_PROXIES].pruned.append(tp_id)
            self.deltas[JOBS].pruned.extend(node.jobs)
            self.deltas[EDGES].pruned.extend(node.edges)
            parent_ids.add(node.first_parent)

        checked_ids = set()
        while parent_ids:
            self._family_ascent_point_prune(
                next(iter(parent_ids)),
                node_ids, parent_ids, checked_ids, self.family_pruned_ids)
        if self.family_pruned_ids:
            self.deltas[FAMILY_PROXIES].pruned.extend(self.family_pruned_ids)
        if node_ids:
            self.pruned_task_proxies.update(node_ids)
            self.updates_pending = True
            self.updates_pending_follow_on = True

    def _family_ascent_point_prune(
            self, fp_id, node_ids, parent_ids, checked_ids, prune_ids):
        """Find and prune family recursively checking child families.

        Recursively map out child families to the bottom from the origin
        family. The work back up to origin checking these families are active.

        """
        fp_data = self.data[self.workflow_id][FAMILY_PROXIES]
        fp_updated = self.updated[FAMILY_PROXIES]
        if fp_id in fp_data:
            fam_node = fp_data[fp_id]
            # Gather child families, then check/update recursively
            for child_id in fam_node.child_families:
                if child_id in checked_ids:
                    continue
                self._family_ascent_point_prune(
                    child_id, node_ids, parent_ids, checked_ids, prune_ids)
            child_tasks = set(fam_node.child_tasks)
            child_families = set(fam_node.child_families)
            # Add in any new children
            if fp_id in fp_updated:
                if fp_updated[fp_id].child_tasks:
                    child_tasks.update(fp_updated[fp_id].child_tasks)
                if fp_updated[fp_id].child_families:
                    child_families.update(fp_updated[fp_id].child_families)
            # if any child tasks or families are in window, don't prune.
            if (
                child_tasks.difference(node_ids)
                or child_families.difference(prune_ids)
            ):
                if (
                    child_tasks.intersection(node_ids)
                    or child_families.intersection(prune_ids)
                ):
                    self.state_update_families.add(fp_id)
            else:
                if fam_node.first_parent:
                    parent_ids.add(fam_node.first_parent)
                # Don't process updated deltas of pruned node
                if fp_id in fp_updated:
                    del fp_updated[fp_id]
                prune_ids.add(fp_id)
        checked_ids.add(fp_id)
        if fp_id in parent_ids:
            parent_ids.remove(fp_id)

    def prune_pruned_updated_nodes(self):
        """Remove updated nodes that will also be pruned this batch.

        This will avoid processing and sending deltas that will immediately
        be pruned. Kept separate from other pruning to allow for update
        information to be included in summaries.

        """
        tp_data = self.data[self.workflow_id][TASK_PROXIES]
        tp_added = self.added[TASK_PROXIES]
        tp_updated = self.updated[TASK_PROXIES]
        j_updated = self.updated[JOBS]
        for tp_id in self.pruned_task_proxies:
            if tp_id in tp_updated:
                if tp_id in tp_data:
                    node = tp_data[tp_id]
                elif tp_id in tp_added:
                    node = tp_added[tp_id]
                else:
                    continue
                update_node = tp_updated.pop(tp_id)
                for j_id in list(node.jobs) + list(update_node.jobs):
                    if j_id in j_updated:
                        del j_updated[j_id]
                self.n_window_edges.difference_update(update_node.edges)
                self.deltas[EDGES].pruned.extend(update_node.edges)
        self.pruned_task_proxies.clear()

    def update_family_proxies(self):
        """Update state & summary of flagged families and ancestors.

        Tasks whose state are updated flag their first parent, as a family
        to be updated, by adding their ID to a set.
        This set is iterated over here until empty, with each members child
        families checked/updated and first parent added to the set (flagged).
        Order doesn't matter, as every family will be checked/updated once at
        most (as an ancestor will-be/has-been added to the set of updated
        families).

        """
        self.updated_state_families.clear()
        while self.state_update_families:
            self._family_ascent_point_update(
                next(iter(self.state_update_families)))
        if self.updated_state_families:
            self.state_update_follow_on = True

    def _family_ascent_point_update(self, fp_id):
        """Updates the given family and children recursively.

        First the child families that haven't been checked/updated are acted
        on first by calling this function. This recursion ends at the family
        first called with this function, which then adds it's first parent
        ancestor to the set of families flagged for update.

        """
        all_nodes = self.all_n_window_nodes
        fp_added = self.added[FAMILY_PROXIES]
        fp_data = self.data[self.workflow_id][FAMILY_PROXIES]
        if fp_id in fp_data:
            fam_node = fp_data[fp_id]
        elif fp_id in fp_added:
            fam_node = fp_added[fp_id]
        else:
            # TODO: Shouldn't need with event driven updates
            # as nodes will be updated before removal.
            if fp_id in self.state_update_families:
                self.updated_state_families.add(fp_id)
                self.state_update_families.remove(fp_id)
            return
        # Gather child families, then check/update recursively
        for child_fam_id in fam_node.child_families:
            if child_fam_id in self.updated_state_families:
                continue
            self._family_ascent_point_update(child_fam_id)
        if fp_id in self.state_update_families:
            fp_updated = self.updated[FAMILY_PROXIES]
            tp_data = self.data[self.workflow_id][TASK_PROXIES]
            tp_updated = self.updated[TASK_PROXIES]
            tp_added = self.added[TASK_PROXIES]
            # Count child family states, set is_held, is_queued, is_runahead
            state_counter = Counter({})
            is_held_total = 0
            is_queued_total = 0
            is_runahead_total = 0
            graph_depth = self.n_edge_distance
            for child_id in fam_node.child_families:
                child_node = fp_updated.get(child_id, fp_data.get(child_id))
                if child_node is not None:
                    is_held_total += child_node.is_held_total
                    is_queued_total += child_node.is_queued_total
                    is_runahead_total += child_node.is_runahead_total
                    state_counter += Counter(dict(child_node.state_totals))
                    if child_node.graph_depth < graph_depth:
                        graph_depth = child_node.graph_depth
            # Gather all child task states
            task_states = []
            for tp_id in fam_node.child_tasks:
                if all_nodes and tp_id not in all_nodes:
                    continue

                tp_delta = tp_updated.get(tp_id)
                tp_node = tp_added.get(tp_id, tp_data.get(tp_id))

                tp_state = tp_delta
                if tp_state is None or not tp_state.HasField('state'):
                    tp_state = tp_node
                if tp_state.state:
                    task_states.append(tp_state.state)

                tp_held = tp_delta
                if tp_held is None or not tp_held.HasField('is_held'):
                    tp_held = tp_node
                if tp_held.is_held:
                    is_held_total += 1

                tp_queued = tp_delta
                if tp_queued is None or not tp_queued.HasField('is_queued'):
                    tp_queued = tp_node
                if tp_queued.is_queued:
                    is_queued_total += 1

                tp_runahead = tp_delta
                if (tp_runahead is None
                        or not tp_runahead.HasField('is_runahead')):
                    tp_runahead = tp_node
                if tp_runahead.is_runahead:
                    is_runahead_total += 1

                tp_depth = tp_delta
                if tp_depth is None or not tp_depth.HasField('graph_depth'):
                    tp_depth = tp_node
                if tp_depth.graph_depth < graph_depth:
                    graph_depth = tp_depth.graph_depth

            state_counter += Counter(task_states)
            # created delta data element
            fp_delta = PbFamilyProxy(
                id=fp_id,
                stamp=f'{fp_id}@{time()}',
                state=extract_group_state(state_counter.keys()),
                is_held=(is_held_total > 0),
                is_held_total=is_held_total,
                is_queued=(is_queued_total > 0),
                is_queued_total=is_queued_total,
                is_runahead=(is_runahead_total > 0),
                is_runahead_total=is_runahead_total,
                graph_depth=graph_depth
            )
            fp_delta.states[:] = state_counter.keys()
            # Use all states to clean up pruned counts
            for state in TASK_STATUSES_ORDERED:
                fp_delta.state_totals[state] = state_counter.get(state, 0)
            fp_updated.setdefault(fp_id, PbFamilyProxy()).MergeFrom(fp_delta)
            # mark as updated in case parent family is updated next
            self.updated_state_families.add(fp_id)
            # mark parent for update
            if fam_node.first_parent:
                self.state_update_families.add(fam_node.first_parent)
            self.state_update_families.remove(fp_id)

    def set_graph_window_extent(self, n_edge_distance: int) -> None:
        """Set what the max edge distance will change to.

        Args:
            n_edge_distance:
                Maximum edge distance from active node.

        """
        if n_edge_distance != self.n_edge_distance:
            self.next_n_edge_distance = n_edge_distance
            self.updates_pending = True

    def update_workflow(self, reloaded=False):
        """Update workflow element status and state totals."""
        # Create new message and copy existing message content
        data = self.data[self.workflow_id]
        w_data = data[WORKFLOW]
        w_delta = self.updated[WORKFLOW]
        delta_set = False

        # new updates/deltas not applied yet
        # so need to search/use updated states if available.
        if self.updated_state_families or self.state_update_follow_on:
            if not self.updated_state_families:
                self.state_update_follow_on = False
            state_counter = Counter({})
            is_held_total = 0
            is_queued_total = 0
            is_runahead_total = 0
            for root_id in set(
                    [n.id
                     for n in data[FAMILY_PROXIES].values()
                     if n.name == 'root'] +
                    [n.id
                     for n in self.added[FAMILY_PROXIES].values()
                     if n.name == 'root']
            ):
                root_node_updated = self.updated[FAMILY_PROXIES].get(root_id)
                if root_node_updated is not None and root_node_updated.state:
                    root_node = root_node_updated
                else:
                    root_node = data[FAMILY_PROXIES].get(root_id)
                if root_node is not None:
                    is_held_total += root_node.is_held_total
                    is_queued_total += root_node.is_queued_total
                    is_runahead_total += root_node.is_runahead_total
                    state_counter += Counter(dict(root_node.state_totals))
            w_delta.states[:] = state_counter.keys()
            for state, state_cnt in state_counter.items():
                w_delta.state_totals[state] = state_cnt

            w_delta.states_updated = True
            w_delta.is_held_total = is_held_total
            w_delta.is_queued_total = is_queued_total
            w_delta.is_runahead_total = is_runahead_total
            delta_set = True

            for state, tp_queue in self.latest_state_tasks.items():
                w_delta.latest_state_tasks[state].task_proxies[:] = tp_queue

        # Set status & msg if changed.
        status = get_workflow_status(self.schd).value
        status_msg = get_workflow_status_msg(self.schd)
        if w_data.status != status or w_data.status_msg != status_msg:
            w_delta.status = status
            w_delta.status_msg = status_msg
            delta_set = True

        if reloaded is not w_data.reloaded:
            w_delta.reloaded = reloaded

        if w_data.n_edge_distance != self.n_edge_distance:
            w_delta.n_edge_distance = self.n_edge_distance
            delta_set = True

        if self.schd.pool.active_tasks:
            pool_points = set(self.schd.pool.active_tasks)

            oldest_point = str(min(pool_points))
            if w_data.oldest_active_cycle_point != oldest_point:
                w_delta.oldest_active_cycle_point = oldest_point
                delta_set = True
            newest_point = str(max(pool_points))
            if w_data.newest_active_cycle_point != newest_point:
                w_delta.newest_active_cycle_point = newest_point
                delta_set = True

        if delta_set:
            w_delta.id = self.workflow_id
            w_delta.last_updated = time()
            w_delta.stamp = f'{w_delta.id}@{w_delta.last_updated}'

    def delta_workflow_ports(self):
        """Set or update the workflow comms ports."""
        w_delta = self.updated[WORKFLOW]
        w_delta.id = self.workflow_id
        w_delta.last_updated = time()
        w_delta.stamp = f'{w_delta.id}@{w_delta.last_updated}'

        w_delta.port = self.schd.server.port
        w_delta.pub_port = self.schd.server.pub_port
        self.updates_pending = True

    def delta_broadcast(self):
        """Collects broadcasts on change event."""
        w_delta = self.updated[WORKFLOW]
        w_delta.id = self.workflow_id
        w_delta.last_updated = time()
        w_delta.stamp = f'{w_delta.id}@{w_delta.last_updated}'

        w_delta.broadcasts = json.dumps(self.schd.broadcast_mgr.broadcasts)
        self._generate_broadcast_node_deltas(
            self.data[self.workflow_id][TASK_PROXIES],
            TASK_PROXIES
        )
        self._generate_broadcast_node_deltas(
            self.added[TASK_PROXIES],
            TASK_PROXIES
        )
        self._generate_broadcast_node_deltas(
            self.data[self.workflow_id][FAMILY_PROXIES],
            FAMILY_PROXIES
        )
        self._generate_broadcast_node_deltas(
            self.added[FAMILY_PROXIES],
            FAMILY_PROXIES
        )

        self.updates_pending = True

    def _generate_broadcast_node_deltas(self, node_data, node_type):
        cfg = self.schd.config.cfg
        for node_id, node in node_data.items():
            tokens = Tokens(node_id)
            new_runtime = runtime_from_config(
                self._apply_broadcasts_to_runtime(
                    tokens,
                    cfg['runtime'][node.name]
                )
            )
            new_sruntime = new_runtime.SerializeToString(
                deterministic=True
            )
            old_sruntime = node.runtime.SerializeToString(
                deterministic=True
            )
            if new_sruntime != old_sruntime:
                node_delta = self.updated[node_type].setdefault(
                    node_id, MESSAGE_MAP[node_type](id=node_id))
                node_delta.runtime.CopyFrom(new_runtime)

    # -----------
    # Task Deltas
    # -----------
    def delta_task_state(self, itask):
        """Create delta for change in task proxy state.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(itask.tokens)
        if not tproxy:
            return
        update_time = time()

        # update task instance
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{update_time}'
        tp_delta.state = itask.state.status
        self.state_update_families.add(tproxy.first_parent)
        if tp_delta.state in self.latest_state_tasks:
            tp_ref = itask.identity
            tp_queue = self.latest_state_tasks[tp_delta.state]
            if tp_ref in tp_queue:
                tp_queue.remove(tp_ref)
            self.latest_state_tasks[tp_delta.state].appendleft(tp_ref)
        # if state is final work out new task mean.
        if tp_delta.state in TASK_STATUSES_FINAL:
            elapsed_time = task_mean_elapsed_time(itask.tdef)
            if elapsed_time:
                t_id = self.definition_id(tproxy.name)
                t_delta = PbTask(
                    stamp=f'{t_id}@{update_time}',
                    mean_elapsed_time=elapsed_time
                )
                self.updated[TASKS].setdefault(
                    t_id,
                    PbTask(id=t_id)).MergeFrom(t_delta)
        self.updates_pending = True

    def delta_task_held(
        self,
        itask: Union[TaskProxy, Tuple[str, 'PointBase', bool]]
    ) -> None:
        """Create delta for change in task proxy held state.

        Args:
            itask:
                The TaskProxy to hold/release OR a tuple of the form
                (name, cycle, is_held).

        """
        if isinstance(itask, TaskProxy):
            tokens = itask.tokens
            is_held = itask.state.is_held
        else:
            name, cycle, is_held = itask
            tokens = self.id_.duplicate(
                task=name,
                cycle=str(cycle),
            )
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(tokens)
        if not tproxy:
            return
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{time()}'
        tp_delta.is_held = is_held
        self.state_update_families.add(tproxy.first_parent)
        self.updates_pending = True

    def delta_task_queued(self, itask: TaskProxy) -> None:
        """Create delta for change in task proxy queued state.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(itask.tokens)
        if not tproxy:
            return
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{time()}'
        tp_delta.is_queued = itask.state.is_queued
        self.state_update_families.add(tproxy.first_parent)
        self.updates_pending = True

    def delta_task_flow_nums(self, itask: TaskProxy) -> None:
        """Create delta for change in task proxy flow_nums.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(itask.tokens)
        if not tproxy:
            return
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{time()}'
        tp_delta.flow_nums = serialise_set(itask.flow_nums)
        self.updates_pending = True

    def delta_task_runahead(self, itask: TaskProxy) -> None:
        """Create delta for change in task proxy runahead state.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(itask.tokens)
        if not tproxy:
            return
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{time()}'
        tp_delta.is_runahead = itask.state.is_runahead
        self.state_update_families.add(tproxy.first_parent)
        self.updates_pending = True

    def delta_task_output(
        self,
        itask: TaskProxy,
        message: str,
    ) -> None:
        """Create delta for change in task proxy output.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(itask.tokens)
        if not tproxy:
            return
        outputs = itask.state.outputs
        label = outputs.get_trigger(message)
        # update task instance
        update_time = time()
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{update_time}'
        output = tp_delta.outputs[label]
        output.label = label
        output.message = message
        output.satisfied = outputs.is_message_complete(message)
        output.time = update_time
        self.updates_pending = True

    def delta_task_outputs(self, itask: TaskProxy) -> None:
        """Create delta for change in all task proxy outputs.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(itask.tokens)
        if not tproxy:
            return
        update_time = time()
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{update_time}'
        for trigger, message, satisfied in itask.state.outputs:
            output = tp_delta.outputs[trigger]
            output.label = trigger
            output.message = message
            output.satisfied = satisfied
            output.time = update_time

        self.updates_pending = True

    def delta_task_prerequisite(self, itask: TaskProxy) -> None:
        """Create delta for change in task proxy prerequisite.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(itask.tokens)
        if not tproxy:
            return
        update_time = time()

        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{update_time}'
        prereq_list = []
        for prereq in itask.state.prerequisites:
            # Protobuf messages populated within
            prereq_obj = prereq.api_dump()
            if prereq_obj:
                prereq_list.append(prereq_obj)
        del tp_delta.prerequisites[:]
        tp_delta.prerequisites.extend(prereq_list)
        self.updates_pending = True

    def delta_task_ext_trigger(
        self,
        itask: TaskProxy,
        trig: str,
        message: str,
        satisfied: bool,
    ) -> None:
        """Create delta for change in task proxy external_trigger.

        Args:
            itask:
                Update task-node from corresponding task proxy
                objects from the workflow task pool.
            trig: Trigger ID.
            message: Trigger message.

        """
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(itask.tokens)
        if not tproxy:
            return
        # update task instance
        update_time = time()
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{update_time}'
        ext_trigger = tp_delta.external_triggers[trig]
        ext_trigger.id = tproxy.external_triggers[trig].id
        ext_trigger.message = message
        ext_trigger.satisfied = satisfied
        ext_trigger.time = update_time
        self.updates_pending = True

    def delta_task_xtrigger(self, sig, satisfied):
        """Create delta for change in task proxy xtrigger.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.
            sig (str): Context of function call (name, args).
            satisfied (bool): Trigger message.

        """
        update_time = time()
        for tp_id, label in self.xtrigger_tasks.get(sig, set()):
            # update task instance
            tp_delta = self.updated[TASK_PROXIES].setdefault(
                tp_id, PbTaskProxy(id=tp_id))
            tp_delta.stamp = f'{tp_id}@{update_time}'
            xtrigger = tp_delta.xtriggers[sig]
            xtrigger.id = sig
            xtrigger.label = label
            xtrigger.satisfied = satisfied
            xtrigger.time = update_time
            self.updates_pending = True

    def delta_from_task_proxy(self, itask: TaskProxy) -> None:
        """Create delta from existing pool task proxy.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tproxy: Optional[PbTaskProxy]
        tp_id, tproxy = self.store_node_fetcher(itask.tokens)
        if not tproxy:
            return
        update_time = time()
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{update_time}'
        self._process_internal_task_proxy(itask, tp_delta)
        self.updates_pending = True

    # -----------
    # Job Deltas
    # -----------
    def delta_job_msg(self, tokens: Tokens, msg: str) -> None:
        """Add message to job."""
        j_id, job = self.store_node_fetcher(tokens)
        if not job:
            return
        j_delta = self.updated[JOBS].setdefault(
            j_id,
            PbJob(id=j_id)
        )
        j_delta.stamp = f'{j_id}@{time()}'
        # in case existing delta has not been processed
        if j_delta.messages:
            j_delta.messages.append(msg)
        else:
            j_delta.messages[:] = job.messages
            j_delta.messages.append(msg)
        self.updates_pending = True

    def delta_job_attr(
        self,
        tokens: Tokens,
        attr_key: str,
        attr_val: Any,
    ) -> None:
        """Set job attribute."""
        j_id, job = self.store_node_fetcher(tokens)
        if not job:
            return
        j_delta = PbJob(stamp=f'{j_id}@{time()}')
        setbuff(j_delta, attr_key, attr_val)
        self.updated[JOBS].setdefault(
            j_id,
            PbJob(id=j_id)
        ).MergeFrom(j_delta)
        self.updates_pending = True

    def delta_job_state(
        self,
        tokens: Tokens,
        status: str,
    ) -> None:
        """Set job state."""
        j_id, job = self.store_node_fetcher(tokens)
        if not job or status not in JOB_STATUS_SET:
            return
        j_delta = PbJob(
            stamp=f'{j_id}@{time()}',
            state=status
        )
        self.updated[JOBS].setdefault(
            j_id,
            PbJob(id=j_id)
        ).MergeFrom(j_delta)
        self.updates_pending = True

    def delta_job_time(
        self,
        tokens: Tokens,
        event_key: str,
        time_str: Optional[str] = None,
    ) -> None:
        """Set an event time in job pool object.

        Set values of both event_key + '_time' and event_key + '_time_string'.
        """
        j_id, job = self.store_node_fetcher(tokens)
        if not job:
            return
        j_delta = PbJob(stamp=f'{j_id}@{time()}')
        time_attr = f'{event_key}_time'
        setbuff(j_delta, time_attr, time_str)
        self.updated[JOBS].setdefault(
            j_id,
            PbJob(id=j_id)
        ).MergeFrom(j_delta)
        self.updates_pending = True

    def store_node_fetcher(self, tokens: Tokens) -> Tuple[str, Any]:
        """Check that task proxy is in or being added to the store"""
        node_type = {
            'task': TASK_PROXIES,
            'job': JOBS,
        }[tokens.lowest_token]
        node_id = tokens.id
        if node_id in self.added[node_type]:
            return (node_id, self.added[node_type][node_id])
        elif node_id in self.data[self.workflow_id][node_type]:
            return (node_id, self.data[self.workflow_id][node_type][node_id])
        return (node_id, False)

    def batch_deltas(self, reloaded=False):
        """Batch gathered deltas."""
        # Gather cumulative update element
        if reloaded:
            self.gather_delta_elements(self.data[self.workflow_id], 'added')
        else:
            self.gather_delta_elements(self.added, 'added')
            self.gather_delta_elements(self.updated, 'updated')

        # set reloaded flag on deltas
        for delta in self.deltas.values():
            if delta.ListFields() or reloaded:
                delta.reloaded = reloaded

    def gather_delta_elements(self, store, delta_type):
        """Gather deltas from store."""
        for key, elements in store.items():
            if elements:
                if key == WORKFLOW:
                    if elements.ListFields():
                        getattr(self.deltas[WORKFLOW], delta_type).CopyFrom(
                            elements)
                    continue
                getattr(self.deltas[key], delta_type).extend(elements.values())

    def apply_delta_batch(self):
        """Apply delta batch to local data-store."""
        data = self.data[self.workflow_id]
        for key, delta in self.deltas.items():
            if delta.ListFields():
                apply_delta(key, delta, data)

    def apply_delta_checksum(self):
        """Construct checksum on deltas for export."""
        data = self.data[self.workflow_id]
        update_time = time()
        for key, delta in self.deltas.items():
            if delta.ListFields():
                delta.time = update_time
                if hasattr(delta, 'checksum'):
                    if key == EDGES:
                        s_att = 'id'
                    else:
                        s_att = 'stamp'
                    delta.checksum = generate_checksum(
                        [getattr(e, s_att)
                         for e in data[key].values()]
                    )

    def clear_delta_batch(self):
        """Clear current deltas."""
        # Potential shared reference, avoid clearing
        self.deltas = {
            EDGES: EDeltas(),
            FAMILIES: FDeltas(),
            FAMILY_PROXIES: FPDeltas(),
            JOBS: JDeltas(),
            TASKS: TDeltas(),
            TASK_PROXIES: TPDeltas(),
            WORKFLOW: WDeltas(),
        }

    def clear_delta_store(self):
        """Clear current delta store."""
        # Potential shared reference, avoid clearing
        self.added = deepcopy(DATA_TEMPLATE)
        self.updated = deepcopy(DATA_TEMPLATE)

    # Message collation and dissemination methods:
    def get_entire_workflow(self):
        """Gather data elements into single Protobuf message.

        Returns:
            cylc.flow.data_messages_pb2.PbEntireWorkflow

        """

        data = self.data[self.workflow_id]

        workflow_msg = PbEntireWorkflow()
        workflow_msg.workflow.CopyFrom(data[WORKFLOW])
        workflow_msg.tasks.extend(data[TASKS].values())
        workflow_msg.task_proxies.extend(data[TASK_PROXIES].values())
        workflow_msg.jobs.extend(data[JOBS].values())
        workflow_msg.families.extend(data[FAMILIES].values())
        workflow_msg.family_proxies.extend(data[FAMILY_PROXIES].values())
        workflow_msg.edges.extend(data[EDGES].values())

        return workflow_msg

    def get_publish_deltas(self):
        """Return deltas for publishing."""
        all_deltas = DELTAS_MAP[ALL_DELTAS]()
        result = []
        for key, delta in self.deltas.items():
            if delta.ListFields():
                result.append(
                    (key.encode('utf-8'), delta, 'SerializeToString'))
                getattr(all_deltas, key).CopyFrom(delta)
        result.append(
            (ALL_DELTAS.encode('utf-8'), all_deltas, 'SerializeToString')
        )
        self.publish_pending = True
        return deepcopy(result)

    def get_data_elements(self, element_type):
        """Get elements of a given type in the form of a delta.

        Args:
            element_type (str):
                Key from DELTAS_MAP dictionary.

        Returns:
            object
                protobuf (DELTAS_MAP[element_type]) message.

        """
        if element_type not in DELTAS_MAP:
            return DELTAS_MAP[WORKFLOW]()
        data = self.data[self.workflow_id]
        pb_msg = DELTAS_MAP[element_type]()
        pb_msg.time = data[WORKFLOW].last_updated
        if element_type == WORKFLOW:
            pb_msg.added.CopyFrom(data[WORKFLOW])
        else:
            pb_msg.added.extend(data[element_type].values())
        return pb_msg

    def definition_id(self, namespace: str) -> str:
        return self.id_.duplicate(cycle=f'$namespace|{namespace}').id

    def edge_id(self, left_tokens: Tokens, right_tokens: Tokens) -> str:
        return self.id_.duplicate(
            cycle=(
                f'$edge|{left_tokens.relative_id}|{right_tokens.relative_id}'
            )
        ).id
