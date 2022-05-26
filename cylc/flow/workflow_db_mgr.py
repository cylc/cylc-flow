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
"""Manage the workflow runtime private and public databases.

This module provides the logic to:
* Create or initialise database file on start up.
* Queue database operations.
* Hide logic that is relevant for database operations.
* Recover public run database file lock.
* Manage existing run database files on restart.
"""

import json
import os
from pkg_resources import parse_version
from shutil import copy, rmtree
from tempfile import mkstemp
from typing import Any, AnyStr, Dict, List, Set, TYPE_CHECKING, Tuple, Union

from cylc.flow import LOG
from cylc.flow.broadcast_report import get_broadcast_change_iter
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.wallclock import get_current_time_string, get_utc_mode
from cylc.flow.exceptions import ServiceFileError
from cylc.flow.util import serialise

if TYPE_CHECKING:
    from cylc.flow.cycling import PointBase
    from cylc.flow.scheduler import Scheduler
    from cylc.flow.task_pool import TaskPool

# # TODO: narrow down Any (should be str | int) after implementing type
# # annotations in cylc.flow.task_state.TaskState
DbArgDict = Dict[str, Any]
DbUpdateTuple = Tuple[DbArgDict, DbArgDict]


PERM_PRIVATE = 0o600  # -rw-------


class WorkflowDatabaseManager:
    """Manage the workflow runtime private and public databases."""

    KEY_INITIAL_CYCLE_POINT = 'icp'
    KEY_INITIAL_CYCLE_POINT_COMPATS = (
        KEY_INITIAL_CYCLE_POINT, 'initial_point')
    KEY_START_CYCLE_POINT = 'startcp'
    KEY_START_CYCLE_POINT_COMPATS = (
        KEY_START_CYCLE_POINT, 'start_point')
    KEY_FINAL_CYCLE_POINT = 'fcp'
    KEY_FINAL_CYCLE_POINT_COMPATS = (KEY_FINAL_CYCLE_POINT, 'final_point')
    KEY_STOP_CYCLE_POINT = 'stopcp'
    KEY_UUID_STR = 'uuid_str'
    KEY_CYLC_VERSION = 'cylc_version'
    KEY_UTC_MODE = 'UTC_mode'
    KEY_PAUSED = 'is_paused'
    KEY_HOLD_CYCLE_POINT = 'holdcp'
    KEY_RUN_MODE = 'run_mode'
    KEY_STOP_CLOCK_TIME = 'stop_clock_time'
    KEY_STOP_TASK = 'stop_task'
    KEY_CYCLE_POINT_FORMAT = 'cycle_point_format'
    KEY_CYCLE_POINT_TIME_ZONE = 'cycle_point_tz'
    KEY_RESTART_COUNT = 'n_restart'

    TABLE_BROADCAST_EVENTS = CylcWorkflowDAO.TABLE_BROADCAST_EVENTS
    TABLE_BROADCAST_STATES = CylcWorkflowDAO.TABLE_BROADCAST_STATES
    TABLE_INHERITANCE = CylcWorkflowDAO.TABLE_INHERITANCE
    TABLE_WORKFLOW_PARAMS = CylcWorkflowDAO.TABLE_WORKFLOW_PARAMS
    TABLE_WORKFLOW_FLOWS = CylcWorkflowDAO.TABLE_WORKFLOW_FLOWS
    TABLE_WORKFLOW_TEMPLATE_VARS = CylcWorkflowDAO.TABLE_WORKFLOW_TEMPLATE_VARS
    TABLE_TASK_ACTION_TIMERS = CylcWorkflowDAO.TABLE_TASK_ACTION_TIMERS
    TABLE_TASK_POOL = CylcWorkflowDAO.TABLE_TASK_POOL
    TABLE_TASK_OUTPUTS = CylcWorkflowDAO.TABLE_TASK_OUTPUTS
    TABLE_TASK_STATES = CylcWorkflowDAO.TABLE_TASK_STATES
    TABLE_TASK_PREREQUISITES = CylcWorkflowDAO.TABLE_TASK_PREREQUISITES
    TABLE_TASK_TIMEOUT_TIMERS = CylcWorkflowDAO.TABLE_TASK_TIMEOUT_TIMERS
    TABLE_TASKS_TO_HOLD = CylcWorkflowDAO.TABLE_TASKS_TO_HOLD
    TABLE_XTRIGGERS = CylcWorkflowDAO.TABLE_XTRIGGERS
    TABLE_ABS_OUTPUTS = CylcWorkflowDAO.TABLE_ABS_OUTPUTS

    def __init__(self, pri_d=None, pub_d=None):
        self.pri_path = None
        if pri_d:
            self.pri_path = os.path.join(
                pri_d, CylcWorkflowDAO.DB_FILE_BASE_NAME)
        self.pub_path = None
        if pub_d:
            self.pub_path = os.path.join(
                pub_d, CylcWorkflowDAO.DB_FILE_BASE_NAME)
        self.pri_dao = None
        self.pub_dao = None

        self.db_deletes_map: Dict[str, List[DbArgDict]] = {
            self.TABLE_BROADCAST_STATES: [],
            self.TABLE_WORKFLOW_PARAMS: [],
            self.TABLE_TASK_POOL: [],
            self.TABLE_TASK_ACTION_TIMERS: [],
            self.TABLE_TASK_OUTPUTS: [],
            self.TABLE_TASK_PREREQUISITES: [],
            self.TABLE_TASK_TIMEOUT_TIMERS: [],
            self.TABLE_TASKS_TO_HOLD: [],
            self.TABLE_XTRIGGERS: []}
        self.db_inserts_map: Dict[str, List[DbArgDict]] = {
            self.TABLE_BROADCAST_EVENTS: [],
            self.TABLE_BROADCAST_STATES: [],
            self.TABLE_INHERITANCE: [],
            self.TABLE_WORKFLOW_PARAMS: [],
            self.TABLE_WORKFLOW_FLOWS: [],
            self.TABLE_WORKFLOW_TEMPLATE_VARS: [],
            self.TABLE_TASK_POOL: [],
            self.TABLE_TASK_ACTION_TIMERS: [],
            self.TABLE_TASK_OUTPUTS: [],
            self.TABLE_TASK_PREREQUISITES: [],
            self.TABLE_TASK_TIMEOUT_TIMERS: [],
            self.TABLE_TASKS_TO_HOLD: [],
            self.TABLE_XTRIGGERS: [],
            self.TABLE_ABS_OUTPUTS: []}
        self.db_updates_map: Dict[str, List[DbUpdateTuple]] = {}

    def copy_pri_to_pub(self) -> None:
        """Copy content of primary database file to public database file."""
        self.pub_dao.close()
        # Use temporary file to ensure that we do not end up with a
        # partial file.
        # If an external connection is locking the old public db, it will
        # still be connected to its inode, but should no longer affect future
        # accesses (hopefully that process will soon recover to give up
        # the lock).
        temp_pub_db_fd, temp_pub_db_file_name = mkstemp(
            prefix=self.pub_dao.DB_FILE_BASE_NAME,
            dir=os.path.dirname(self.pub_dao.db_file_name)
        )
        os.close(temp_pub_db_fd)
        try:
            # Create the file if it didn't exist; this is done in the hope of
            # addressing potential NFS file lag, we think
            open(self.pub_dao.db_file_name, "a").close()  # noqa: SIM115
            # Get default permissions level for public db:
            st_mode = os.stat(self.pub_dao.db_file_name).st_mode

            copy(self.pri_dao.db_file_name, temp_pub_db_file_name)
            os.rename(temp_pub_db_file_name, self.pub_dao.db_file_name)
            os.chmod(self.pub_dao.db_file_name, st_mode)
        except OSError:
            if os.path.exists(temp_pub_db_file_name):
                os.remove(temp_pub_db_file_name)
            raise

    def delete_workflow_params(self, *keys):
        """Schedule deletion of rows from workflow_params table by keys."""
        for key in keys:
            self.db_deletes_map[self.TABLE_WORKFLOW_PARAMS].append(
                {'key': key}
            )

    def delete_workflow_paused(self):
        """Delete paused status."""
        self.delete_workflow_params(self.KEY_PAUSED)

    def delete_workflow_hold_cycle_point(self):
        """Delete workflow hold cycle point."""
        self.delete_workflow_params(self.KEY_HOLD_CYCLE_POINT)

    def delete_workflow_stop_clock_time(self):
        """Delete workflow stop clock time from workflow_params table."""
        self.delete_workflow_params(self.KEY_STOP_CLOCK_TIME)

    def delete_workflow_stop_cycle_point(self):
        """Delete workflow stop cycle point from workflow_params table."""
        self.delete_workflow_params(self.KEY_STOP_CYCLE_POINT)

    def delete_workflow_stop_task(self):
        """Delete workflow stop task from workflow_params table."""
        self.delete_workflow_params(self.KEY_STOP_TASK)

    def get_pri_dao(self):
        """Return the primary DAO."""
        return CylcWorkflowDAO(self.pri_path)

    @staticmethod
    def _namedtuple2json(obj):
        """Convert nametuple obj to a JSON string.

        Arguments:
            obj (namedtuple): input object to serialize to JSON.

        Return (str):
            Serialized JSON string of input object in the form "[type, list]".
        """
        if obj is None:
            return json.dumps(None)
        else:
            return json.dumps([type(obj).__name__, obj.__getnewargs__()])

    def on_workflow_start(self, is_restart):
        """Initialise data access objects.

        Ensure that:
        * private database file is private
        * public database is in sync with private database
        """
        if not is_restart:
            try:
                os.unlink(self.pri_path)
            except OSError:
                # Just in case the path is a directory!
                rmtree(self.pri_path, ignore_errors=True)
        self.pri_dao = self.get_pri_dao()
        os.chmod(self.pri_path, PERM_PRIVATE)
        self.pub_dao = CylcWorkflowDAO(self.pub_path, is_public=True)
        self.copy_pri_to_pub()

    def on_workflow_shutdown(self):
        """Close data access objects."""
        if self.pri_dao:
            self.pri_dao.close()
            self.pri_dao = None
        if self.pub_dao:
            self.pub_dao.close()
            self.pub_dao = None

    def process_queued_ops(self) -> None:
        """Handle queued db operations for each task proxy."""
        if self.pri_dao is None or self.pub_dao is None:
            return
        # Record workflow parameters and tasks in pool
        # Record any broadcast settings to be dumped out
        if any(self.db_deletes_map.values()):
            for table_name, db_deletes in sorted(
                    self.db_deletes_map.items()):
                while db_deletes:
                    where_args = db_deletes.pop(0)
                    self.pri_dao.add_delete_item(table_name, where_args)
                    self.pub_dao.add_delete_item(table_name, where_args)
        if any(self.db_inserts_map.values()):
            for table_name, db_inserts in sorted(
                    self.db_inserts_map.items()):
                while db_inserts:
                    db_insert = db_inserts.pop(0)
                    self.pri_dao.add_insert_item(table_name, db_insert)
                    self.pub_dao.add_insert_item(table_name, db_insert)
        if (hasattr(self, 'db_updates_map') and
                any(self.db_updates_map.values())):
            for table_name, db_updates in sorted(
                    self.db_updates_map.items()):
                while db_updates:
                    set_args, where_args = db_updates.pop(0)
                    self.pri_dao.add_update_item(
                        table_name, set_args, where_args)
                    self.pub_dao.add_update_item(
                        table_name, set_args, where_args)

        # Previously, we used a separate thread for database writes. This has
        # now been removed. For the private database, there is no real
        # advantage in using a separate thread as it needs to be always in sync
        # with what is current. For the public database, which does not need to
        # be fully in sync, there is some advantage of using a separate
        # thread/process, if writing to it becomes a bottleneck. At the moment,
        # there is no evidence that this is a bottleneck, so it is better to
        # keep the logic simple.
        self.pri_dao.execute_queued_items()
        self.pub_dao.execute_queued_items()

    def put_broadcast(self, modified_settings, is_cancel=False):
        """Put or clear broadcasts in runtime database."""
        now = get_current_time_string(display_sub_seconds=True)
        for broadcast_change in (
                get_broadcast_change_iter(modified_settings, is_cancel)):
            broadcast_change["time"] = now
            self.db_inserts_map[self.TABLE_BROADCAST_EVENTS].append(
                broadcast_change)
            if is_cancel:
                self.db_deletes_map[self.TABLE_BROADCAST_STATES].append({
                    "point": broadcast_change["point"],
                    "namespace": broadcast_change["namespace"],
                    "key": broadcast_change["key"]})
                # Delete statements are currently executed before insert
                # statements, so we should clear out any insert statements that
                # are deleted here.
                # (Not the most efficient logic here, but unless we have a
                # large number of inserts, then this should not be a big
                # concern.)
                inserts = []
                for insert in self.db_inserts_map[self.TABLE_BROADCAST_STATES]:
                    if any(insert[key] != broadcast_change[key]
                           for key in ["point", "namespace", "key"]):
                        inserts.append(insert)
                self.db_inserts_map[self.TABLE_BROADCAST_STATES] = inserts
            else:
                self.db_inserts_map[self.TABLE_BROADCAST_STATES].append({
                    "point": broadcast_change["point"],
                    "namespace": broadcast_change["namespace"],
                    "key": broadcast_change["key"],
                    "value": broadcast_change["value"]})

    def put_runtime_inheritance(self, config):
        """Put task/family inheritance in runtime database."""
        for namespace in config.cfg['runtime']:
            value = config.runtime['linearized ancestors'][namespace]
            self.db_inserts_map[self.TABLE_INHERITANCE].append({
                "namespace": namespace,
                "inheritance": json.dumps(value)})

    def put_workflow_params(self, schd: 'Scheduler') -> None:
        """Put various workflow parameters from schd in runtime database.

        This method queues the relevant insert statements.

        Arguments:
            schd (cylc.flow.scheduler.Scheduler): scheduler object.
        """
        self.db_deletes_map[self.TABLE_WORKFLOW_PARAMS].append({})
        self.db_inserts_map[self.TABLE_WORKFLOW_PARAMS].extend([
            {"key": self.KEY_UUID_STR, "value": schd.uuid_str},
            {"key": self.KEY_CYLC_VERSION, "value": CYLC_VERSION},
            {"key": self.KEY_UTC_MODE, "value": get_utc_mode()},
        ])
        if schd.config.cycle_point_dump_format is not None:
            self.put_workflow_params_1(
                self.KEY_CYCLE_POINT_FORMAT,
                schd.config.cycle_point_dump_format
            )
        if schd.is_paused:
            self.put_workflow_params_1(self.KEY_PAUSED, 1)
        for key in (
            self.KEY_INITIAL_CYCLE_POINT,
            self.KEY_FINAL_CYCLE_POINT,
            self.KEY_START_CYCLE_POINT,
            self.KEY_STOP_CYCLE_POINT
        ):
            value = getattr(schd.options, key, None)
            if value is not None and value != 'reload':
                self.put_workflow_params_1(key, value)
        for key in (
            self.KEY_RUN_MODE,
            self.KEY_CYCLE_POINT_TIME_ZONE
        ):
            value = getattr(schd.options, key, None)
            if value is not None:
                self.put_workflow_params_1(key, value)
        for key in (
            self.KEY_STOP_CLOCK_TIME,
            self.KEY_STOP_TASK
        ):
            value = getattr(schd, key, None)
            if value is not None:
                self.put_workflow_params_1(key, value)

    def put_workflow_params_1(
        self, key: str, value: Union[AnyStr, float]
    ) -> None:
        """Queue insertion of 1 key=value pair to the workflow_params table."""
        self.db_inserts_map[self.TABLE_WORKFLOW_PARAMS].append(
            {"key": key, "value": value}
        )

    def put_workflow_paused(self):
        """Put workflow paused flag to workflow_params table."""
        self.put_workflow_params_1(self.KEY_PAUSED, 1)

    def put_workflow_hold_cycle_point(self, value):
        """Put workflow hold cycle point to workflow_params table."""
        self.put_workflow_params_1(self.KEY_HOLD_CYCLE_POINT, str(value))

    def put_workflow_stop_clock_time(self, value):
        """Put workflow stop clock time to workflow_params table."""
        self.put_workflow_params_1(self.KEY_STOP_CLOCK_TIME, value)

    def put_workflow_stop_cycle_point(self, value):
        """Put workflow stop cycle point to workflow_params table."""
        self.put_workflow_params_1(self.KEY_STOP_CYCLE_POINT, value)

    def put_workflow_stop_task(self, value):
        """Put workflow stop task to workflow_params table."""
        self.put_workflow_params_1(self.KEY_STOP_TASK, value)

    def put_workflow_template_vars(self, template_vars):
        """Put template_vars in runtime database.

        This method queues the relevant insert statements.
        """
        for key, value in template_vars.items():
            self.db_inserts_map[self.TABLE_WORKFLOW_TEMPLATE_VARS].append(
                {"key": key, "value": repr(value)})

    def put_task_event_timers(self, task_events_mgr):
        """Put statements to update the task_action_timers table."""
        if task_events_mgr.event_timers_updated:
            self.db_deletes_map[self.TABLE_TASK_ACTION_TIMERS].append({})
            for key, timer in task_events_mgr._event_timers.items():
                key1, point, name, submit_num = key
                self.db_inserts_map[self.TABLE_TASK_ACTION_TIMERS].append({
                    "name": name,
                    "cycle": point,
                    "ctx_key": json.dumps((key1, submit_num,)),
                    "ctx": self._namedtuple2json(timer.ctx),
                    "delays": json.dumps(timer.delays),
                    "num": timer.num,
                    "delay": timer.delay,
                    "timeout": timer.timeout
                })
            task_events_mgr.event_timers_updated = False

    def put_xtriggers(self, sat_xtrig):
        """Put statements to update external triggers table."""
        self.db_deletes_map[self.TABLE_XTRIGGERS].append({})
        for sig, res in sat_xtrig.items():
            self.db_inserts_map[self.TABLE_XTRIGGERS].append({
                "signature": sig,
                "results": json.dumps(res)})

    def put_update_task_state(self, itask):
        """Update task_states table for current state of itask.

        For final event-driven update before removing finished tasks.
        No need to update task_pool table as finished tasks are immediately
        removed from the pool.
        """
        set_args = {
            "time_updated": itask.state.time_updated,
            "status": itask.state.status,
            "flow_wait": itask.flow_wait
        }
        where_args = {
            "cycle": str(itask.point),
            "name": itask.tdef.name,
            "flow_nums": serialise(itask.flow_nums),
            "submit_num": itask.submit_num,
        }
        self.db_updates_map.setdefault(self.TABLE_TASK_STATES, [])
        self.db_updates_map[self.TABLE_TASK_STATES].append(
            (set_args, where_args))

    def put_task_pool(self, pool: 'TaskPool') -> None:
        """Update various task tables for current pool, in runtime database.

        Queue delete (everything) statements to wipe the tables, and queue the
        relevant insert statements for the current tasks in the pool.
        """
        self.db_deletes_map[self.TABLE_TASK_POOL].append({})
        # Comment this out to retain the trigger-time prereq status of past
        # tasks (but then the prerequisite table will grow indefinitely):
        self.db_deletes_map[self.TABLE_TASK_PREREQUISITES].append({})
        # This should already be done by self.put_task_event_timers above:
        # self.db_deletes_map[self.TABLE_TASK_ACTION_TIMERS].append({})
        self.db_deletes_map[self.TABLE_TASK_TIMEOUT_TIMERS].append({})
        for itask in pool.get_all_tasks():
            for prereq in itask.state.prerequisites:
                for (p_cycle, p_name, p_output), satisfied_state in (
                    prereq.satisfied.items()
                ):
                    self.put_insert_task_prerequisites(itask, {
                        "flow_nums": serialise(itask.flow_nums),
                        "prereq_name": p_name,
                        "prereq_cycle": p_cycle,
                        "prereq_output": p_output,
                        "satisfied": satisfied_state
                    })
            self.db_inserts_map[self.TABLE_TASK_POOL].append({
                "name": itask.tdef.name,
                "cycle": str(itask.point),
                "flow_nums": serialise(itask.flow_nums),
                "status": itask.state.status,
                "is_held": itask.state.is_held
            })
            if itask.timeout is not None:
                self.db_inserts_map[self.TABLE_TASK_TIMEOUT_TIMERS].append({
                    "name": itask.tdef.name,
                    "cycle": str(itask.point),
                    "timeout": itask.timeout
                })
            if itask.poll_timer is not None:
                self.db_inserts_map[self.TABLE_TASK_ACTION_TIMERS].append({
                    "name": itask.tdef.name,
                    "cycle": str(itask.point),
                    "ctx_key": json.dumps("poll_timer"),
                    "ctx": self._namedtuple2json(itask.poll_timer.ctx),
                    "delays": json.dumps(itask.poll_timer.delays),
                    "num": itask.poll_timer.num,
                    "delay": itask.poll_timer.delay,
                    "timeout": itask.poll_timer.timeout
                })
            for ctx_key_1, timer in itask.try_timers.items():
                if timer is None:
                    continue
                self.db_inserts_map[self.TABLE_TASK_ACTION_TIMERS].append({
                    "name": itask.tdef.name,
                    "cycle": str(itask.point),
                    "ctx_key": json.dumps(("try_timers", ctx_key_1)),
                    "ctx": self._namedtuple2json(timer.ctx),
                    "delays": json.dumps(timer.delays),
                    "num": timer.num,
                    "delay": timer.delay,
                    "timeout": timer.timeout
                })
            if itask.state.time_updated:
                set_args = {
                    "time_updated": itask.state.time_updated,
                    "submit_num": itask.submit_num,
                    "try_num": itask.get_try_num(),
                    "status": itask.state.status
                }
                where_args = {
                    "cycle": str(itask.point),
                    "name": itask.tdef.name,
                    "flow_nums": serialise(itask.flow_nums)
                }
                self.db_updates_map.setdefault(self.TABLE_TASK_STATES, [])
                self.db_updates_map[self.TABLE_TASK_STATES].append(
                    (set_args, where_args)
                )
                itask.state.time_updated = None

    def put_tasks_to_hold(
        self, tasks: Set[Tuple[str, 'PointBase']]
    ) -> None:
        """Replace the tasks in the tasks_to_hold table."""
        # There isn't that much cost in calling this multiple times between
        # processing of the db queue (when the db queue is eventually
        # processed, the SQL commands only get run once). Still, replacing the
        # whole table each time the queue is processed is a bit ineffecient.
        self.db_deletes_map[self.TABLE_TASKS_TO_HOLD] = [{}]
        self.db_inserts_map[self.TABLE_TASKS_TO_HOLD] = [
            {"name": name, "cycle": str(point)}
            for name, point in tasks
        ]

    def put_insert_task_events(self, itask, args):
        """Put INSERT statement for task_events table."""
        self._put_insert_task_x(CylcWorkflowDAO.TABLE_TASK_EVENTS, itask, args)

    def put_insert_task_late_flags(self, itask):
        """If itask is late, put INSERT statement to task_late_flags table."""
        if itask.is_late:
            self._put_insert_task_x(
                CylcWorkflowDAO.TABLE_TASK_LATE_FLAGS, itask, {"value": True})

    def put_insert_task_jobs(self, itask, args):
        """Put INSERT statement for task_jobs table."""
        self._put_insert_task_x(CylcWorkflowDAO.TABLE_TASK_JOBS, itask, args)

    def put_insert_task_states(self, itask, args):
        """Put INSERT statement for task_states table."""
        self._put_insert_task_x(CylcWorkflowDAO.TABLE_TASK_STATES, itask, args)

    def put_insert_task_prerequisites(self, itask, args):
        """Put INSERT statement for task_prerequisites table."""
        self._put_insert_task_x(self.TABLE_TASK_PREREQUISITES, itask, args)

    def put_insert_task_outputs(self, itask):
        """Reset outputs for a task."""
        self._put_insert_task_x(
            CylcWorkflowDAO.TABLE_TASK_OUTPUTS,
            itask,
            {
                "flow_nums": serialise(itask.flow_nums),
                "outputs": json.dumps([])
            }
        )

    def put_insert_abs_output(self, cycle, name, output):
        """Put INSERT statement for a new abs output."""
        args = {
            "cycle": str(cycle),
            "name": name,
            "output": output
        }
        self.db_inserts_map.setdefault(CylcWorkflowDAO.TABLE_ABS_OUTPUTS, [])
        self.db_inserts_map[CylcWorkflowDAO.TABLE_ABS_OUTPUTS].append(args)

    def put_insert_workflow_flows(self, flow_num, flow_metadata):
        """Put INSERT statement for a new flow."""
        self.db_inserts_map.setdefault(
            CylcWorkflowDAO.TABLE_WORKFLOW_FLOWS, []
        )
        self.db_inserts_map[CylcWorkflowDAO.TABLE_WORKFLOW_FLOWS].append(
            {
                "flow_num": flow_num,
                "start_time": flow_metadata["start_time"],
                "description": flow_metadata["description"],
            }
        )

    def _put_insert_task_x(self, table_name, itask, args):
        """Put INSERT statement for a task_* table."""
        args.update({
            "name": itask.tdef.name,
            "cycle": str(itask.point)})
        if "submit_num" not in args:
            args["submit_num"] = itask.submit_num
        self.db_inserts_map.setdefault(table_name, [])
        self.db_inserts_map[table_name].append(args)

    def put_update_task_jobs(self, itask, set_args):
        """Put UPDATE statement for task_jobs table."""
        self._put_update_task_x(
            CylcWorkflowDAO.TABLE_TASK_JOBS, itask, set_args)

    def put_update_task_outputs(self, itask):
        """Put UPDATE statement for task_outputs table."""
        outputs = []
        for _, message in itask.state.outputs.get_completed_all():
            outputs.append(message)
        set_args = {
            "outputs": json.dumps(outputs)
        }
        where_args = {
            "cycle": str(itask.point),
            "name": itask.tdef.name,
            "flow_nums": serialise(itask.flow_nums),
        }
        self.db_updates_map.setdefault(self.TABLE_TASK_OUTPUTS, [])
        self.db_updates_map[self.TABLE_TASK_OUTPUTS].append(
            (set_args, where_args))

    def _put_update_task_x(self, table_name, itask, set_args):
        """Put UPDATE statement for a task_* table."""
        where_args = {
            "cycle": str(itask.point),
            "name": itask.tdef.name}
        if "submit_num" not in set_args:
            where_args["submit_num"] = itask.submit_num
        if "flow_nums" not in set_args:
            where_args["flow_nums"] = serialise(itask.flow_nums)
        self.db_updates_map.setdefault(table_name, [])
        self.db_updates_map[table_name].append((set_args, where_args))

    def recover_pub_from_pri(self):
        """Recover public database from private database."""
        if self.pub_dao.n_tries >= self.pub_dao.MAX_TRIES:
            self.copy_pri_to_pub()
            LOG.warning(
                f"{self.pub_dao.db_file_name}: recovered from "
                f"{self.pri_dao.db_file_name}")
            self.pub_dao.n_tries = 0

    def restart_check(self) -> bool:
        """Check & vacuum the runtime DB for a restart.

        Raises ServiceFileError if DB is incompatible.

        Returns False if DB doesn't exist, else True.
        """
        try:
            self.check_workflow_db_compatibility()
        except FileNotFoundError:
            return False
        except ServiceFileError as exc:
            raise ServiceFileError(f"Cannot restart - {exc}")
        pri_dao = self.get_pri_dao()
        try:
            pri_dao.vacuum()
            self.n_restart = pri_dao.select_workflow_params_restart_count() + 1
            self.put_workflow_params_1(self.KEY_RESTART_COUNT, self.n_restart)
        finally:
            pri_dao.close()
        return True

    def check_workflow_db_compatibility(self):
        """Raises ServiceFileError if the existing workflow database is
        incompatible with the current version of Cylc."""
        if not os.path.isfile(self.pri_path):
            raise FileNotFoundError(self.pri_path)
        incompat_msg = (
            f"Workflow database is incompatible with Cylc {CYLC_VERSION}"
        )
        manual_rm_msg = (
            "If you are sure you want to operate on this workflow, please "
            f"delete the database file at {self.pri_path}"
        )
        pri_dao = self.get_pri_dao()
        try:
            last_run_ver = pri_dao.connect().execute(
                rf'''
                    SELECT
                        value
                    FROM
                        {self.TABLE_WORKFLOW_PARAMS}
                    WHERE
                        key == ?
                ''',  # nosec (table name is a code constant)
                [self.KEY_CYLC_VERSION]
            ).fetchone()[0]
        except TypeError:
            raise ServiceFileError(
                f"{incompat_msg}, or is corrupted.\n{manual_rm_msg}"
            )
        finally:
            pri_dao.close()
        last_run_ver = parse_version(last_run_ver)
        restart_incompat_ver = parse_version(
            CylcWorkflowDAO.RESTART_INCOMPAT_VERSION
        )
        if last_run_ver <= restart_incompat_ver:
            raise ServiceFileError(
                f"{incompat_msg} (workflow last run with Cylc {last_run_ver})."
                f"\n{manual_rm_msg}"
            )
