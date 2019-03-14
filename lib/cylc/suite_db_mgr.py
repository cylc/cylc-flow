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
"""Manage the suite runtime private and public databases.

This module provides the logic to:
* Create or initialise database file on start up.
* Queue database operations.
* Hide logic that is relevant for database operations.
* Recover public run database file lock.
* Manage existing run database files on restart.
"""

import json
import os
from shutil import copy, rmtree
from tempfile import mkstemp


from cylc import LOG
from cylc.broadcast_report import get_broadcast_change_iter
from cylc.rundb import CylcSuiteDAO
from cylc import __version__ as CYLC_VERSION
from cylc.wallclock import get_current_time_string, get_utc_mode


class SuiteDatabaseManager(object):
    """Manage the suite runtime private and public databases."""

    TABLE_BROADCAST_EVENTS = CylcSuiteDAO.TABLE_BROADCAST_EVENTS
    TABLE_BROADCAST_STATES = CylcSuiteDAO.TABLE_BROADCAST_STATES
    TABLE_CHECKPOINT_ID = CylcSuiteDAO.TABLE_CHECKPOINT_ID
    TABLE_INHERITANCE = CylcSuiteDAO.TABLE_INHERITANCE
    TABLE_SUITE_PARAMS = CylcSuiteDAO.TABLE_SUITE_PARAMS
    TABLE_SUITE_TEMPLATE_VARS = CylcSuiteDAO.TABLE_SUITE_TEMPLATE_VARS
    TABLE_TASK_ACTION_TIMERS = CylcSuiteDAO.TABLE_TASK_ACTION_TIMERS
    TABLE_TASK_POOL = CylcSuiteDAO.TABLE_TASK_POOL
    TABLE_TASK_OUTPUTS = CylcSuiteDAO.TABLE_TASK_OUTPUTS
    TABLE_TASK_STATES = CylcSuiteDAO.TABLE_TASK_STATES
    TABLE_TASK_TIMEOUT_TIMERS = CylcSuiteDAO.TABLE_TASK_TIMEOUT_TIMERS
    TABLE_XTRIGGERS = CylcSuiteDAO.TABLE_XTRIGGERS

    def __init__(self, pri_d=None, pub_d=None):
        self.pri_path = None
        if pri_d:
            self.pri_path = os.path.join(pri_d, CylcSuiteDAO.DB_FILE_BASE_NAME)
        self.pub_path = None
        if pub_d:
            self.pub_path = os.path.join(pub_d, CylcSuiteDAO.DB_FILE_BASE_NAME)
        self.pri_dao = None
        self.pub_dao = None

        self.db_deletes_map = {
            self.TABLE_BROADCAST_STATES: [],
            self.TABLE_SUITE_PARAMS: [],
            self.TABLE_TASK_POOL: [],
            self.TABLE_TASK_ACTION_TIMERS: [],
            self.TABLE_TASK_OUTPUTS: [],
            self.TABLE_TASK_TIMEOUT_TIMERS: [],
            self.TABLE_XTRIGGERS: []}
        self.db_inserts_map = {
            self.TABLE_BROADCAST_EVENTS: [],
            self.TABLE_BROADCAST_STATES: [],
            self.TABLE_INHERITANCE: [],
            self.TABLE_SUITE_PARAMS: [],
            self.TABLE_SUITE_TEMPLATE_VARS: [],
            self.TABLE_CHECKPOINT_ID: [],
            self.TABLE_TASK_POOL: [],
            self.TABLE_TASK_ACTION_TIMERS: [],
            self.TABLE_TASK_OUTPUTS: [],
            self.TABLE_TASK_TIMEOUT_TIMERS: [],
            self.TABLE_XTRIGGERS: []}
        self.db_updates_map = {}

    def checkpoint(self, name):
        """Checkpoint the task pool, etc."""
        return self.pri_dao.take_checkpoints(name, other_daos=[self.pub_dao])

    def copy_pri_to_pub(self):
        """Copy content of primary database file to public database file.

        Use temporary file to ensure that we do not end up with a partial file.

        """
        temp_pub_db_file_name = None
        self.pub_dao.close()
        try:
            self.pub_dao.conn = None  # reset connection
            open(self.pub_dao.db_file_name, "a").close()  # touch
            st_mode = os.stat(self.pub_dao.db_file_name).st_mode
            temp_pub_db_file_name = mkstemp(
                prefix=self.pub_dao.DB_FILE_BASE_NAME,
                dir=os.path.dirname(self.pub_dao.db_file_name))[1]
            copy(self.pri_dao.db_file_name, temp_pub_db_file_name)
            os.rename(temp_pub_db_file_name, self.pub_dao.db_file_name)
            os.chmod(self.pub_dao.db_file_name, st_mode)
        except (IOError, OSError):
            if temp_pub_db_file_name:
                os.unlink(temp_pub_db_file_name)
            raise

    def get_pri_dao(self):
        """Return the primary DAO."""
        return CylcSuiteDAO(self.pri_path)

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

    def on_suite_start(self, is_restart):
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
        os.chmod(self.pri_path, 0o600)
        self.pub_dao = CylcSuiteDAO(self.pub_path, is_public=True)
        self.copy_pri_to_pub()

    def on_suite_shutdown(self):
        """Close data access objects."""
        if self.pri_dao:
            self.pri_dao.close()
            self.pri_dao = None
        if self.pub_dao:
            self.pub_dao.close()
            self.pub_dao = None

    def process_queued_ops(self):
        """Handle queued db operations for each task proxy."""
        if self.pri_dao is None:
            return
        # Record suite parameters and tasks in pool
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

    def put_suite_params(self, schd):
        """Put various suite parameters from schd in runtime database.

        This method queues the relevant insert statements.

        Arguments:
            schd (cylc.scheduler.Scheduler): scheduler object.
        """
        if schd.final_point is None:
            # Store None as proper null value in database. No need to do this
            # for initial cycle point, which should never be None.
            final_point_str = None
        else:
            final_point_str = str(schd.final_point)
        self.db_inserts_map[self.TABLE_SUITE_PARAMS].extend([
            {"key": "uuid_str", "value": str(schd.uuid_str)},
            {"key": "run_mode", "value": schd.run_mode},
            {"key": "cylc_version", "value": CYLC_VERSION},
            {"key": "UTC_mode", "value": get_utc_mode()},
            {"key": "initial_point", "value": str(schd.initial_point)},
            {"key": "final_point", "value": final_point_str},
        ])
        if schd.config.cfg['cylc']['cycle point format']:
            self.db_inserts_map[self.TABLE_SUITE_PARAMS].append({
                "key": "cycle_point_format",
                "value": schd.config.cfg['cylc']['cycle point format']})
        if schd.pool.is_held:
            self.db_inserts_map[self.TABLE_SUITE_PARAMS].append({
                "key": "is_held", "value": 1})
        if schd.cli_start_point_string:
            self.db_inserts_map[self.TABLE_SUITE_PARAMS].append({
                "key": "start_point", "value": schd.cli_start_point_string})

    def put_suite_template_vars(self, template_vars):
        """Put template_vars in runtime database.

        This method queues the relevant insert statements.
        """
        for key, value in template_vars.items():
            self.db_inserts_map[self.TABLE_SUITE_TEMPLATE_VARS].append(
                {"key": key, "value": value})

    def put_task_event_timers(self, task_events_mgr):
        """Put statements to update the task_action_timers table."""
        if task_events_mgr.event_timers:
            self.db_deletes_map[self.TABLE_TASK_ACTION_TIMERS].append({})
            for key, timer in task_events_mgr.event_timers.items():
                key1, point, name, submit_num = key
                self.db_inserts_map[self.TABLE_TASK_ACTION_TIMERS].append({
                    "name": name,
                    "cycle": point,
                    "ctx_key": json.dumps((key1, submit_num,)),
                    "ctx": self._namedtuple2json(timer.ctx),
                    "delays": json.dumps(timer.delays),
                    "num": timer.num,
                    "delay": timer.delay,
                    "timeout": timer.timeout})

    def put_xtriggers(self, sat_xtrig):
        """Put statements to update external triggers table."""
        self.db_deletes_map[self.TABLE_XTRIGGERS].append({})
        for sig, res in sat_xtrig.items():
            self.db_inserts_map[self.TABLE_XTRIGGERS].append({
                "signature": sig,
                "results": json.dumps(res)})

    def put_task_pool(self, pool):
        """Put statements to update the task_pool table in runtime database.

        Update the task_pool table and the task_action_timers table.
        Queue delete (everything) statements to wipe the tables, and queue the
        relevant insert statements for the current tasks in the pool.
        """
        self.db_deletes_map[self.TABLE_TASK_POOL].append({})
        # No need to do:
        # self.db_deletes_map[self.TABLE_TASK_ACTION_TIMERS].append({})
        # Should already be done by self.put_task_event_timers above.
        self.db_deletes_map[self.TABLE_TASK_TIMEOUT_TIMERS].append({})
        for itask in pool.get_all_tasks():
            self.db_inserts_map[self.TABLE_TASK_POOL].append({
                "name": itask.tdef.name,
                "cycle": str(itask.point),
                "spawned": int(itask.has_spawned),
                "status": itask.state.status,
                "hold_swap": itask.state.hold_swap})
            if itask.timeout is not None:
                self.db_inserts_map[self.TABLE_TASK_TIMEOUT_TIMERS].append({
                    "name": itask.tdef.name,
                    "cycle": str(itask.point),
                    "timeout": itask.timeout})
            if itask.poll_timer is not None:
                self.db_inserts_map[self.TABLE_TASK_ACTION_TIMERS].append({
                    "name": itask.tdef.name,
                    "cycle": str(itask.point),
                    "ctx_key": json.dumps("poll_timer"),
                    "ctx": self._namedtuple2json(itask.poll_timer.ctx),
                    "delays": json.dumps(itask.poll_timer.delays),
                    "num": itask.poll_timer.num,
                    "delay": itask.poll_timer.delay,
                    "timeout": itask.poll_timer.timeout})
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
                    "timeout": timer.timeout})
            if itask.state.time_updated:
                set_args = {
                    "time_updated": itask.state.time_updated,
                    "submit_num": itask.submit_num,
                    "try_num": itask.get_try_num(),
                    "status": itask.state.status}
                where_args = {
                    "cycle": str(itask.point),
                    "name": itask.tdef.name,
                }
                self.db_updates_map.setdefault(self.TABLE_TASK_STATES, [])
                self.db_updates_map[self.TABLE_TASK_STATES].append(
                    (set_args, where_args))
                itask.state.time_updated = None

        self.db_inserts_map[self.TABLE_CHECKPOINT_ID].append({
            # id = -1 for latest
            "id": CylcSuiteDAO.CHECKPOINT_LATEST_ID,
            "time": get_current_time_string(),
            "event": CylcSuiteDAO.CHECKPOINT_LATEST_EVENT})

    def put_insert_task_events(self, itask, args):
        """Put INSERT statement for task_events table."""
        self._put_insert_task_x(CylcSuiteDAO.TABLE_TASK_EVENTS, itask, args)

    def put_insert_task_late_flags(self, itask):
        """If itask is late, put INSERT statement to task_late_flags table."""
        if itask.is_late:
            self._put_insert_task_x(
                CylcSuiteDAO.TABLE_TASK_LATE_FLAGS, itask, {"value": True})

    def put_insert_task_jobs(self, itask, args):
        """Put INSERT statement for task_jobs table."""
        self._put_insert_task_x(CylcSuiteDAO.TABLE_TASK_JOBS, itask, args)

    def put_insert_task_states(self, itask, args):
        """Put INSERT statement for task_states table."""
        self._put_insert_task_x(CylcSuiteDAO.TABLE_TASK_STATES, itask, args)

    def put_insert_task_outputs(self, itask):
        """Reset custom outputs for a task."""
        self._put_insert_task_x(CylcSuiteDAO.TABLE_TASK_OUTPUTS, itask, {})

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
            CylcSuiteDAO.TABLE_TASK_JOBS, itask, set_args)

    def put_update_task_outputs(self, itask):
        """Put UPDATE statement for task_outputs table."""
        items = {}
        for trigger, message in itask.state.outputs.get_completed_customs():
            items[trigger] = message
        self._put_update_task_x(
            CylcSuiteDAO.TABLE_TASK_OUTPUTS,
            itask, {"outputs": json.dumps(items)})

    def _put_update_task_x(self, table_name, itask, set_args):
        """Put UPDATE statement for a task_* table."""
        where_args = {
            "cycle": str(itask.point),
            "name": itask.tdef.name}
        if "submit_num" not in set_args:
            where_args["submit_num"] = itask.submit_num
        self.db_updates_map.setdefault(table_name, [])
        self.db_updates_map[table_name].append((set_args, where_args))

    def recover_pub_from_pri(self):
        """Recover public database from private database."""
        if self.pub_dao.n_tries >= self.pub_dao.MAX_TRIES:
            self.copy_pri_to_pub()
            LOG.warning(
                "%(pub_db_name)s: recovered from %(pri_db_name)s" % {
                    "pub_db_name": self.pub_dao.db_file_name,
                    "pri_db_name": self.pri_dao.db_file_name})
            self.pub_dao.n_tries = 0

    def restart_upgrade(self):
        """Vacuum/upgrade runtime DB on restart."""
        pri_dao = self.get_pri_dao()
        pri_dao.vacuum()
        pri_dao.close()
