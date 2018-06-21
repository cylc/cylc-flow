#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
"""Provide data access object for the suite runtime database."""

import json
import sqlite3
import sys
import traceback
import os
import tarfile
import re
from glob import glob

import cylc.flags
from cylc.wallclock import get_current_time_string
from cylc.suite_logging import LOG, ERR
from cylc.task_state import TASK_STATUS_GROUPS


class CylcSuiteDAOTableColumn(object):
    """Represent a column in a table."""

    __slots__ = ('name', 'datatype', 'is_primary_key')

    def __init__(self, name, datatype, is_primary_key):
        self.name = name
        self.datatype = datatype
        self.is_primary_key = is_primary_key


class CylcSuiteDAOTable(object):
    """Represent a table in the suite runtime database."""

    FMT_CREATE = "CREATE TABLE %(name)s(%(columns_str)s%(primary_keys_str)s)"
    FMT_DELETE = "DELETE FROM %(name)s%(where_str)s"
    FMT_INSERT = "INSERT OR REPLACE INTO %(name)s VALUES(%(values_str)s)"
    FMT_UPDATE = "UPDATE %(name)s SET %(set_str)s%(where_str)s"

    __slots__ = ('name', 'columns', 'delete_queues', 'insert_queue',
                 'update_queues')

    def __init__(self, name, column_items):
        self.name = name
        self.columns = []
        for column_item in column_items:
            name = column_item[0]
            attrs = {}
            if len(column_item) > 1:
                attrs = column_item[1]
            self.columns.append(CylcSuiteDAOTableColumn(
                name,
                attrs.get("datatype", "TEXT"),
                attrs.get("is_primary_key", False)))
        self.delete_queues = {}
        self.insert_queue = []
        self.update_queues = {}

    def get_create_stmt(self):
        """Return an SQL statement to create this table."""
        column_str_list = []
        primary_keys = []
        for column in self.columns:
            column_str_list.append(column.name + " " + column.datatype)
            if column.is_primary_key:
                primary_keys.append(column.name)
        primary_keys_str = ""
        if primary_keys:
            primary_keys_str = ", PRIMARY KEY(" + ", ".join(primary_keys) + ")"
        return self.FMT_CREATE % {
            "name": self.name,
            "columns_str": ", ".join(column_str_list),
            "primary_keys_str": primary_keys_str}

    def get_insert_stmt(self):
        """Return an SQL statement to insert a row to this table."""
        return self.FMT_INSERT % {
            "name": self.name,
            "values_str": ", ".join("?" * len(self.columns))}

    def add_delete_item(self, where_args):
        """Queue a DELETE item.

        where_args should be a dict, delete will only apply to rows matching
        all these items.

        """
        stmt_args = []
        where_str = ""
        if where_args:
            where_strs = []
            for column in self.columns:
                if column.name in where_args:
                    where_strs.append(column.name + "==?")
                    stmt_args.append(where_args[column.name])
            if where_strs:
                where_str = " WHERE " + " AND ".join(where_strs)
        stmt = self.FMT_DELETE % {"name": self.name, "where_str": where_str}
        if stmt not in self.delete_queues:
            self.delete_queues[stmt] = []
        self.delete_queues[stmt].append(stmt_args)

    def add_insert_item(self, args):
        """Queue an INSERT args.

        If args is a list, its length will be adjusted to be the same as the
        number of columns. If args is a dict, will return a list with the same
        length as the number of columns, the elements of which are determined
        by matching the column names with the keys in the dict.

        Empty elements are padded with None.

        """
        if isinstance(args, list):
            if len(args) == len(self.columns):
                stmt_args = list(args)
            elif len(args) < len(self.columns):
                stmt_args = args + [None] * (len(self.columns) - len(args))
            else:  # len(args) > len(self.columns)
                stmt_args = args[0:len(self.columns)]
        else:
            stmt_args = [
                args.get(column.name, None) for column in self.columns]
        self.insert_queue.append(stmt_args)

    def add_update_item(self, set_args, where_args):
        """Queue an UPDATE item.

        set_args should be a dict, with colum keys and values to be set.
        where_args should be a dict, update will only apply to rows matching
        all these items.

        """
        set_strs = []
        stmt_args = []
        for column in self.columns:
            if column.name in set_args:
                set_strs.append(column.name + "=?")
                stmt_args.append(set_args[column.name])
        set_str = ", ".join(set_strs)
        where_str = ""
        if where_args:
            where_strs = []
            for column in self.columns:
                if column.name in where_args:
                    where_strs.append(column.name + "==?")
                    stmt_args.append(where_args[column.name])
            if where_strs:
                where_str = " WHERE " + " AND ".join(where_strs)
        stmt = self.FMT_UPDATE % {
            "name": self.name,
            "set_str": set_str,
            "where_str": where_str}
        if stmt not in self.update_queues:
            self.update_queues[stmt] = []
        self.update_queues[stmt].append(stmt_args)


class CylcSuiteDAO(object):
    """Data access object for the suite runtime database."""

    CONN_TIMEOUT = 0.2
    DB_FILE_BASE_NAME = "db"
    OLD_DB_FILE_BASE_NAME = "cylc-suite.db"
    OLD_DB_FILE_BASE_NAME_611 = (
        "cylc-suite-private.db", "cylc-suite-public.db")
    MAX_TRIES = 100
    CHECKPOINT_LATEST_ID = 0
    CHECKPOINT_LATEST_EVENT = "latest"
    TABLE_BROADCAST_EVENTS = "broadcast_events"
    TABLE_BROADCAST_STATES = "broadcast_states"
    TABLE_BROADCAST_STATES_CHECKPOINTS = "broadcast_states_checkpoints"
    TABLE_INHERITANCE = "inheritance"
    TABLE_SUITE_PARAMS = "suite_params"
    TABLE_SUITE_PARAMS_CHECKPOINTS = "suite_params_checkpoints"
    TABLE_SUITE_TEMPLATE_VARS = "suite_template_vars"
    TABLE_TASK_JOBS = "task_jobs"
    TABLE_TASK_EVENTS = "task_events"
    TABLE_TASK_ACTION_TIMERS = "task_action_timers"
    TABLE_CHECKPOINT_ID = "checkpoint_id"
    TABLE_TASK_LATE_FLAGS = "task_late_flags"
    TABLE_TASK_OUTPUTS = "task_outputs"
    TABLE_TASK_POOL = "task_pool"
    TABLE_TASK_POOL_CHECKPOINTS = "task_pool_checkpoints"
    TABLE_TASK_STATES = "task_states"
    TABLE_TASK_TIMEOUT_TIMERS = "task_timeout_timers"
    TABLE_XTRIGGERS = "xtriggers"

    TABLES_ATTRS = {
        TABLE_BROADCAST_EVENTS: [
            ["time"],
            ["change"],
            ["point"],
            ["namespace"],
            ["key"],
            ["value"],
        ],
        TABLE_BROADCAST_STATES: [
            ["point", {"is_primary_key": True}],
            ["namespace", {"is_primary_key": True}],
            ["key", {"is_primary_key": True}],
            ["value"],
        ],
        TABLE_BROADCAST_STATES_CHECKPOINTS: [
            ["id", {"datatype": "INTEGER", "is_primary_key": True}],
            ["point", {"is_primary_key": True}],
            ["namespace", {"is_primary_key": True}],
            ["key", {"is_primary_key": True}],
            ["value"],
        ],
        TABLE_CHECKPOINT_ID: [
            ["id", {"datatype": "INTEGER", "is_primary_key": True}],
            ["time"],
            ["event"],
        ],
        TABLE_INHERITANCE: [
            ["namespace", {"is_primary_key": True}],
            ["inheritance"],
        ],
        TABLE_SUITE_PARAMS: [
            ["key", {"is_primary_key": True}],
            ["value"],
        ],
        TABLE_SUITE_PARAMS_CHECKPOINTS: [
            ["id", {"datatype": "INTEGER", "is_primary_key": True}],
            ["key", {"is_primary_key": True}],
            ["value"],
        ],
        TABLE_SUITE_TEMPLATE_VARS: [
            ["key", {"is_primary_key": True}],
            ["value"],
        ],
        TABLE_TASK_ACTION_TIMERS: [
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["ctx_key", {"is_primary_key": True}],
            ["ctx"],
            ["delays"],
            ["num", {"datatype": "INTEGER"}],
            ["delay"],
            ["timeout"],
        ],
        TABLE_TASK_JOBS: [
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["submit_num", {"datatype": "INTEGER", "is_primary_key": True}],
            ["is_manual_submit", {"datatype": "INTEGER"}],
            ["try_num", {"datatype": "INTEGER"}],
            ["time_submit"],
            ["time_submit_exit"],
            ["submit_status", {"datatype": "INTEGER"}],
            ["time_run"],
            ["time_run_exit"],
            ["run_signal"],
            ["run_status", {"datatype": "INTEGER"}],
            ["user_at_host"],
            ["batch_sys_name"],
            ["batch_sys_job_id"],
        ],
        TABLE_TASK_EVENTS: [
            ["name"],
            ["cycle"],
            ["time"],
            ["submit_num", {"datatype": "INTEGER"}],
            ["event"],
            ["message"],
        ],
        TABLE_TASK_LATE_FLAGS: [
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["value", {"datatype": "INTEGER"}],
        ],
        TABLE_TASK_OUTPUTS: [
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["outputs"],
        ],
        TABLE_TASK_POOL: [
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["spawned", {"datatype": "INTEGER"}],
            ["status"],
            ["hold_swap"],
        ],
        TABLE_XTRIGGERS: [
            ["signature", {"is_primary_key": True}],
            ["results"],
        ],
        TABLE_TASK_POOL_CHECKPOINTS: [
            ["id", {"datatype": "INTEGER", "is_primary_key": True}],
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["spawned", {"datatype": "INTEGER"}],
            ["status"],
            ["hold_swap"],
        ],
        TABLE_TASK_STATES: [
            ["name", {"is_primary_key": True}],
            ["cycle", {"is_primary_key": True}],
            ["time_created"],
            ["time_updated"],
            ["submit_num", {"datatype": "INTEGER"}],
            ["status"],
        ],
        TABLE_TASK_TIMEOUT_TIMERS: [
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["timeout", {"datatype": "REAL"}],
        ],
    }

    def __init__(self, db_file_name=None, is_public=False):
        """Initialise object.

        db_file_name - Path to the database file
        is_public - If True, allow retries, etc

        """
        self.db_file_name = db_file_name
        self.is_public = is_public
        self.conn = None
        self.n_tries = 0

        self.tables = {}
        for name, attrs in sorted(self.TABLES_ATTRS.items()):
            self.tables[name] = CylcSuiteDAOTable(name, attrs)

        if not self.is_public:
            self.create_tables()

    def add_delete_item(self, table_name, where_args=None):
        """Queue a DELETE item for a given table.

        where_args should be a dict, update will only apply to rows matching
        all these items.

        """
        self.tables[table_name].add_delete_item(where_args)

    def add_insert_item(self, table_name, args):
        """Queue an INSERT args for a given table.

        If args is a list, its length will be adjusted to be the same as the
        number of columns. If args is a dict, will return a list with the same
        length as the number of columns, the elements of which are determined
        by matching the column names with the keys in the dict.

        Empty elements are padded with None.

        """
        self.tables[table_name].add_insert_item(args)

    def add_update_item(self, table_name, set_args, where_args=None):
        """Queue an UPDATE item for a given table.

        set_args should be a dict, with colum keys and values to be set.
        where_args should be a dict, update will only apply to rows matching
        all these items.

        """
        self.tables[table_name].add_update_item(set_args, where_args)

    def close(self):
        """Explicitly close the connection."""
        if self.conn is not None:
            try:
                self.conn.close()
            except sqlite3.Error:
                pass
            self.conn = None

    def connect(self):
        """Connect to the database."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_file_name, self.CONN_TIMEOUT)
        return self.conn

    def create_tables(self):
        """Create tables."""
        names = []
        for row in self.connect().execute(
                "SELECT name FROM sqlite_master WHERE type==? ORDER BY name",
                ["table"]):
            names.append(row[0])
        cur = None
        for name, table in self.tables.items():
            if name not in names:
                cur = self.conn.execute(table.get_create_stmt())
        if cur is not None:
            self.conn.commit()

    def execute_queued_items(self):
        """Execute queued items for each table."""
        try:
            for table in self.tables.values():
                # DELETE statements may have varying number of WHERE args so we
                # can only executemany for each identical template statement.
                for stmt, stmt_args_list in table.delete_queues.items():
                    self._execute_stmt(stmt, stmt_args_list)
                # INSERT statements are uniform for each table, so all INSERT
                # statements can be executed using a single "executemany" call.
                if table.insert_queue:
                    self._execute_stmt(
                        table.get_insert_stmt(), table.insert_queue)
                # UPDATE statements can have varying number of SET and WHERE
                # args so we can only executemany for each identical template
                # statement.
                for stmt, stmt_args_list in table.update_queues.items():
                    self._execute_stmt(stmt, stmt_args_list)
            # Connection should only be opened if we have executed something.
            if self.conn is None:
                return
            self.conn.commit()
        except sqlite3.Error:
            if not self.is_public:
                raise
            self.n_tries += 1
            LOG.warning(
                "%(file)s: write attempt (%(attempt)d) did not complete\n" % {
                    "file": self.db_file_name, "attempt": self.n_tries})
            if self.conn is not None:
                try:
                    self.conn.rollback()
                except sqlite3.Error:
                    pass
            return
        else:
            # Clear the queues
            for table in self.tables.values():
                table.delete_queues.clear()
                del table.insert_queue[:]  # list.clear avail from Python 3.3
                table.update_queues.clear()
            # Report public database retry recovery if necessary
            if self.n_tries:
                LOG.warning(
                    "%(file)s: recovered after (%(attempt)d) attempt(s)\n" % {
                        "file": self.db_file_name, "attempt": self.n_tries})
            self.n_tries = 0
        finally:
            # Note: This is not strictly necessary. However, if the suite run
            # directory is removed, a forced reconnection to the private
            # database will ensure that the suite dies.
            self.close()

    def _execute_stmt(self, stmt, stmt_args_list):
        """Helper for "self.execute_queued_items".

        Execute a statement. If this is the public database, return True on
        success and False on failure. If this is the private database, return
        True on success, and raise on failure.
        """
        try:
            self.connect()
            self.conn.executemany(stmt, stmt_args_list)
        except sqlite3.Error:
            if not self.is_public:
                raise
            if cylc.flags.debug:
                traceback.print_exc()
            err_log = (
                "cannot execute database statement:\n"
                "file=%(file)s:\nstmt=%(stmt)s"
            ) % {"file": self.db_file_name, "stmt": stmt}
            for i, stmt_args in enumerate(stmt_args_list):
                err_log += ("\nstmt_args[%(i)d]=%(stmt_args)s" % {
                    "i": i, "stmt_args": stmt_args})
            LOG.warning(err_log)
            raise

    def pre_select_broadcast_states(self, id_key=None, order=None):
        """Query statement and args formation for select_broadcast_states."""
        form_stmt = r"SELECT point,namespace,key,value FROM %s"
        if order == "ASC":
            ordering = " ORDER BY point ASC, namespace ASC, key ASC"
            form_stmt = form_stmt + ordering
        if id_key is None or id_key == self.CHECKPOINT_LATEST_ID:
            return form_stmt % self.TABLE_BROADCAST_STATES, []
        else:
            return (form_stmt % self.TABLE_BROADCAST_STATES_CHECKPOINTS +
                    r" WHERE id==?"), [id_key]

    def select_broadcast_states(self, callback, id_key=None, sort=None):
        """Select from broadcast_states or broadcast_states_checkpoints.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [point, namespace, key, value]

        If id_key is specified,
        select from broadcast_states table if id_key == CHECKPOINT_LATEST_ID.
        Otherwise select from broadcast_states_checkpoints where id == id_key.
        """
        stmt, stmt_args = pre_select_broadcast_states(self, id_key=None,
                                                      order=sort)
        for row_idx, row in enumerate(self.connect().execute(stmt, stmt_args)):
            callback(row_idx, list(row))

    def pre_select_broadcast_events(self, order=None):
        """Query statement and args formation for select_broadcast_events."""
        form_stmt = r"SELECT point,namespace,key,value FROM %s"
        if order == "DESC":
            ordering = (" ORDER BY " +
                        "time DESC, point DESC, namespace DESC, key DESC")
            form_stmt = form_stmt + ordering
        return form_stmt % self.TABLE_BROADCAST_EVENTS, []

    def select_broadcast_events(self, callback, id_key=None, sort=None):
        """Select from broadcast_events.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [time, change, point, namespace, key, value]
        """
        stmt, stmt_args = pre_select_broadcast_events(self, order=sort)
        for row_idx, row in enumerate(self.connect().execute(stmt, stmt_args)):
            callback(row_idx, list(row))

    def select_checkpoint_id(self, callback, id_key=None):
        """Select from checkpoint_id.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [id, time, event]

        If id_key is specified, add where id == id_key to select.
        """
        stmt = r"SELECT id,time,event FROM %s" % self.TABLE_CHECKPOINT_ID
        stmt_args = []
        if id_key is not None:
            stmt += r" WHERE id==?"
            stmt_args.append(id_key)
        stmt += r"  ORDER BY time ASC"
        for row_idx, row in enumerate(self.connect().execute(stmt, stmt_args)):
            callback(row_idx, list(row))

    def select_suite_params(self, callback, id_key=None):
        """Select from suite_params or suite_params_checkpoints.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [key,value]

        If id_key is specified,
        select from suite_params table if id_key == CHECKPOINT_LATEST_ID.
        Otherwise select from suite_params_checkpoints where id == id_key.
        """
        form_stmt = r"SELECT key,value FROM %s"
        if id_key is None or id_key == self.CHECKPOINT_LATEST_ID:
            stmt = form_stmt % self.TABLE_SUITE_PARAMS
            stmt_args = []
        else:
            stmt = (form_stmt % self.TABLE_SUITE_PARAMS_CHECKPOINTS +
                    r" WHERE id==?")
            stmt_args = [id_key]
        for row_idx, row in enumerate(self.connect().execute(stmt, stmt_args)):
            callback(row_idx, list(row))

    def select_suite_template_vars(self, callback):
        """Select from suite_template_vars.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [key,value]
        """
        for row_idx, row in enumerate(self.connect().execute(
                r"SELECT key,value FROM %s" % self.TABLE_SUITE_TEMPLATE_VARS)):
            callback(row_idx, list(row))

    def select_table_schema(self, my_type, my_name):
        """Select from task_action_timers for restart.

        Invoke callback(row_idx, row) on each row.
        """
        for sql, in self.connect().execute(
                r"SELECT sql FROM sqlite_master where type==? and name==?",
                [my_type, my_name]):
            return sql

    def select_task_action_timers(self, callback):
        """Select from task_action_timers for restart.

        Invoke callback(row_idx, row) on each row.
        """
        attrs = []
        for item in self.TABLES_ATTRS[self.TABLE_TASK_ACTION_TIMERS]:
            attrs.append(item[0])
        stmt = r"SELECT %s FROM %s" % (
            ",".join(attrs), self.TABLE_TASK_ACTION_TIMERS)
        for row_idx, row in enumerate(self.connect().execute(stmt)):
            callback(row_idx, list(row))

    def select_task_job(self, keys, cycle, name, submit_num=None):
        """Select items from task_jobs by (cycle, name, submit_num).

        Return a dict for mapping keys to the column values.

        """
        if keys is None:
            keys = []
            for column in self.tables[self.TABLE_TASK_JOBS].columns[3:]:
                keys.append(column.name)
        if submit_num in [None, "NN"]:
            stmt = (r"SELECT %(keys_str)s FROM %(table)s"
                    r" WHERE cycle==? AND name==?"
                    r" ORDER BY submit_num DESC LIMIT 1") % {
                "keys_str": ",".join(keys),
                "table": self.TABLE_TASK_JOBS}
            stmt_args = [cycle, name]
        else:
            stmt = (r"SELECT %(keys_str)s FROM %(table)s"
                    r" WHERE cycle==? AND name==? AND submit_num==?") % {
                "keys_str": ",".join(keys),
                "table": self.TABLE_TASK_JOBS}
            stmt_args = [cycle, name, submit_num]
        try:
            for row in self.connect().execute(stmt, stmt_args):
                ret = {}
                for key, value in zip(keys, row):
                    ret[key] = value
                return ret
        except sqlite3.DatabaseError:
            return None

    def select_task_job_run_times(self, callback):
        """Select run times of succeeded task jobs grouped by task names.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [name, run_times_str]

        where run_times_str is a string containing comma separated list of
        integer run times. This method is used to re-populate elapsed run times
        of each task on restart.
        """
        stmt = (
            r"SELECT"
            r" name,"
            r" GROUP_CONCAT("
            r"     CAST(strftime('%s', time_run_exit) AS NUMERIC) -"
            r"     CAST(strftime('%s', time_run) AS NUMERIC))"
            r" FROM task_jobs"
            r" WHERE run_status==0 GROUP BY name ORDER BY time_run_exit")
        for row_idx, row in enumerate(self.connect().execute(stmt)):
            callback(row_idx, list(row))

    def select_submit_nums_for_insert(self, task_ids):
        """Select name,cycle,submit_num from task_states.

        Fetch submit numbers for tasks on insert.
        Return a data structure like this:

        {
            (name1, point1): submit_num,
            ...,
        }

        task_ids should be specified as [(name-glob, cycle), ...]

        """
        stmt = r"SELECT name,cycle,submit_num FROM %(name)s" % {
            "name": self.TABLE_TASK_STATES}
        stmt_args = []
        if task_ids:
            stmt += (
                " WHERE (" +
                ") OR (".join(["name GLOB ? AND cycle==?"] * len(task_ids)) +
                ")")
            for name, cycle in task_ids:
                stmt_args += [name, cycle]
        ret = {}
        for name, cycle, submit_num in self.connect().execute(stmt, stmt_args):
            ret[(name, cycle)] = submit_num
        return ret

    def select_xtriggers_for_restart(self, callback):
        stm = r"SELECT signature,results FROM %s" % self.TABLE_XTRIGGERS
        for row_idx, row in enumerate(self.connect().execute(stm, [])):
            callback(row_idx, list(row))

    def select_task_pool(self, callback, id_key=None):
        """Select from task_pool or task_pool_checkpoints.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [cycle, name, spawned, status]

        If id_key is specified,
        select from task_pool table if id_key == CHECKPOINT_LATEST_ID.
        Otherwise select from task_pool_checkpoints where id == id_key.
        """
        form_stmt = r"SELECT cycle,name,spawned,status,hold_swap FROM %s"
        if id_key is None or id_key == self.CHECKPOINT_LATEST_ID:
            stmt = form_stmt % self.TABLE_TASK_POOL
            stmt_args = []
        else:
            stmt = (
                form_stmt % self.TABLE_TASK_POOL_CHECKPOINTS + r" WHERE id==?")
            stmt_args = [id_key]
        for row_idx, row in enumerate(self.connect().execute(stmt, stmt_args)):
            callback(row_idx, list(row))

    def select_task_pool_for_restart(self, callback, id_key=None):
        """Select from task_pool+task_states+task_jobs for restart.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [cycle, name, spawned, is_late, status, hold_swap, submit_num,
             try_num, user_at_host, time_submit, time_run, timeout, outputs]

        If id_key is specified,
        select from task_pool table if id_key == CHECKPOINT_LATEST_ID.
        Otherwise select from task_pool_checkpoints where id == id_key.
        """
        form_stmt = r"""
            SELECT
                %(task_pool)s.cycle,
                %(task_pool)s.name,
                %(task_pool)s.spawned,
                %(task_late_flags)s.value,
                %(task_pool)s.status,
                %(task_pool)s.hold_swap,
                %(task_states)s.submit_num,
                %(task_jobs)s.try_num,
                %(task_jobs)s.user_at_host,
                %(task_jobs)s.time_submit,
                %(task_jobs)s.time_run,
                %(task_timeout_timers)s.timeout,
                %(task_outputs)s.outputs
            FROM
                %(task_pool)s
            JOIN
                %(task_states)s
            ON  %(task_pool)s.cycle == %(task_states)s.cycle AND
                %(task_pool)s.name == %(task_states)s.name
            LEFT OUTER JOIN
                %(task_late_flags)s
            ON  %(task_pool)s.cycle == %(task_late_flags)s.cycle AND
                %(task_pool)s.name == %(task_late_flags)s.name
            LEFT OUTER JOIN
                %(task_jobs)s
            ON  %(task_pool)s.cycle == %(task_jobs)s.cycle AND
                %(task_pool)s.name == %(task_jobs)s.name AND
                %(task_states)s.submit_num == %(task_jobs)s.submit_num
            LEFT OUTER JOIN
                %(task_timeout_timers)s
            ON  %(task_pool)s.cycle == %(task_timeout_timers)s.cycle AND
                %(task_pool)s.name == %(task_timeout_timers)s.name
            LEFT OUTER JOIN
                %(task_outputs)s
            ON  %(task_pool)s.cycle == %(task_outputs)s.cycle AND
                %(task_pool)s.name == %(task_outputs)s.name
        """
        form_data = {
            "task_pool": self.TABLE_TASK_POOL,
            "task_states": self.TABLE_TASK_STATES,
            "task_late_flags": self.TABLE_TASK_LATE_FLAGS,
            "task_timeout_timers": self.TABLE_TASK_TIMEOUT_TIMERS,
            "task_jobs": self.TABLE_TASK_JOBS,
            "task_outputs": self.TABLE_TASK_OUTPUTS,
        }
        if id_key is None or id_key == self.CHECKPOINT_LATEST_ID:
            stmt = form_stmt % form_data
            stmt_args = []
        else:
            form_data["task_pool"] = self.TABLE_TASK_POOL_CHECKPOINTS
            stmt = (form_stmt + r" WHERE %(task_pool)s.id==?") % form_data
            stmt_args = [id_key]
        for row_idx, row in enumerate(self.connect().execute(stmt, stmt_args)):
            callback(row_idx, list(row))

    def select_task_times(self):
        """Select submit/start/stop times to compute job timings.

        To make data interpretation easier, choose the most recent succeeded
        task to sample timings from.
        """
        q = """
            SELECT
                name,
                cycle,
                user_at_host,
                batch_sys_name,
                time_submit,
                time_run,
                time_run_exit
            FROM
                %(task_jobs)s
            WHERE
                run_status = %(succeeded)d
        """ % {
            'task_jobs': self.TABLE_TASK_JOBS,
            'succeeded': 0,
        }
        columns = (
            'name', 'cycle', 'host', 'batch_system',
            'submit_time', 'start_time', 'succeed_time'
        )
        return columns, [r for r in self.connect().execute(q)]

    def take_checkpoints(self, event, other_daos=None):
        """Add insert items to *_checkpoints tables.

        Select items in suite_params, broadcast_states and task_pool and
        prepare them for insert into the relevant *_checkpoints tables, and
        prepare an insert into the checkpoint_id table the event and the
        current time.

        If other_daos is a specified, it should be a list of CylcSuiteDAO
        objects.  The logic will prepare insertion of the same items into the
        *_checkpoints tables of these DAOs as well.
        """
        id_ = 1
        for max_id, in self.connect().execute(
                "SELECT MAX(id) FROM %(table)s" %
                {"table": self.TABLE_CHECKPOINT_ID}):
            if max_id >= id_:
                id_ = max_id + 1
        daos = [self]
        if other_daos:
            daos.extend(other_daos)
        for dao in daos:
            dao.tables[self.TABLE_CHECKPOINT_ID].add_insert_item([
                id_, get_current_time_string(), event])
        for table_name in [
                self.TABLE_SUITE_PARAMS,
                self.TABLE_BROADCAST_STATES,
                self.TABLE_TASK_POOL]:
            for row in self.connect().execute("SELECT * FROM %s" % table_name):
                for dao in daos:
                    dao.tables[table_name + "_checkpoints"].add_insert_item(
                        [id_] + list(row))

    def upgrade_from_611(self):
        """Upgrade database on restart with a 6.11.X private database."""
        conn = self.connect()
        # Add hold_swap column task_pool(_checkpoints) tables
        for t_name in [self.TABLE_TASK_POOL, self.TABLE_TASK_POOL_CHECKPOINTS]:
            sys.stdout.write("Add hold_swap column to %s\n" % (t_name,))
            conn.execute(
                r"ALTER TABLE " + t_name + r" ADD COLUMN hold_swap TEXT")
        conn.commit()

    def upgrade_with_state_file(self, state_file_path):
        """Upgrade database on restart with an old state file.

        Upgrade database from a state file generated by a suite that ran with
        an old cylc version.
        """
        check_points = []
        self.select_checkpoint_id(
            lambda row_idx, row: check_points.append(row),
            self.CHECKPOINT_LATEST_ID)
        if check_points:
            # No need to upgrade if latest check point already exists
            return
        sys.stdout.write("Upgrading suite db with %s ...\n" % state_file_path)
        self._upgrade_with_state_file_states(state_file_path)
        self._upgrade_with_state_file_extras()

    def _upgrade_with_state_file_states(self, state_file_path):
        """Helper for self.upgrade_with_state_file().

        Populate the new database tables with information from state file.
        """
        location = None
        sys.stdout.write("Populating %s table" % self.TABLE_SUITE_PARAMS)
        for line in open(state_file_path):
            line = line.strip()
            if location is None:
                # run mode, time stamp, initial cycle, final cycle
                location = self._upgrade_with_state_file_header(line)
            elif location == "broadcast":
                # Ignore broadcast pickle in state file.
                # The "broadcast_states" table should already be populated.
                if line == "Begin task states":
                    location = "task states"
                    sys.stdout.write(
                        "\nPopulating %s table" % self.TABLE_TASK_POOL)
            else:
                self._upgrade_with_state_file_tasks(line)
        sys.stdout.write("\n")
        self.execute_queued_items()

    def _upgrade_with_state_file_header(self, line):
        """Parse a header line in state file, add information to DB."""
        head, tail = line.split(" : ", 1)
        if head == "time":
            self.add_insert_item(self.TABLE_CHECKPOINT_ID, {
                "id": self.CHECKPOINT_LATEST_ID,
                "time": tail.split(" ", 1)[0],
                "event": self.CHECKPOINT_LATEST_EVENT})
            return
        for name, key in [
                ("run mode", "run_mode"),
                ("initial cycle", "initial_point"),
                ("final cycle", "final_point")]:
            if tail == "None":
                tail = None
            if head == name:
                self.add_insert_item(self.TABLE_SUITE_PARAMS, {
                    "key": key,
                    "value": tail})
                sys.stdout.write("\n + %s=%s" % (key, tail))
                if name == "final cycle":
                    return "broadcast"
                else:
                    return

    def _upgrade_with_state_file_tasks(self, line):
        """Parse a task state line in state file, add information to DB."""
        head, tail = line.split(" : ", 1)
        name, cycle = head.split(".")
        status = None
        spawned = None
        for item in tail.split(", "):
            key, value = item.split("=", 1)
            if key == "status":
                status = value
            elif key == "spawned":
                spawned = int(value in ["True", "true"])
        self.add_insert_item(self.TABLE_TASK_POOL, {
            "name": name,
            "cycle": cycle,
            "spawned": spawned,
            "status": status,
            "hold_swap": None})
        sys.stdout.write("\n + %s" % head)

    def _upgrade_with_state_file_extras(self):
        """Upgrade the database tables after reading in state file."""
        conn = self.connect()

        # Rename old tables
        for t_name in [self.TABLE_TASK_STATES, self.TABLE_TASK_EVENTS]:
            conn.execute(
                r"ALTER TABLE " + t_name +
                r" RENAME TO " + t_name + "_old")
        conn.commit()

        # Create tables with new columns
        self.create_tables()

        # Populate new tables using old column data
        for t_name in [self.TABLE_TASK_STATES, self.TABLE_TASK_EVENTS]:
            sys.stdout.write(r"Upgrading %s table " % (t_name))
            column_names = [col.name for col in self.tables[t_name].columns]
            for i, row in enumerate(conn.execute(
                    r"SELECT " + ",".join(column_names) +
                    " FROM " + t_name + "_old")):
                # These tables can be big, so we don't want to queue the items
                # in memory.
                conn.execute(self.tables[t_name].get_insert_stmt(), list(row))
                if i:
                    sys.stdout.write("\b" * len("%d rows" % (i)))
                sys.stdout.write("%d rows" % (i + 1))
            sys.stdout.write(" done\n")
        conn.commit()

        # Drop old tables
        for t_name in [self.TABLE_TASK_STATES, self.TABLE_TASK_EVENTS]:
            conn.execute(r"DROP TABLE " + t_name + "_old")
        conn.commit()

    def vacuum(self):
        """Vacuum to the database."""
        return self.connect().execute("VACUUM")


class CylcReviewDAO(object):
    """Cylc Review data access object to the suite runtime database."""

    JOB_STATUS_COMBOS = {
        "all": "",
        "submitted": "submit_status == 0 AND time_run IS NULL",
        "submitted,running": "submit_status == 0 AND run_status IS NULL",
        "submission-failed": "submit_status == 1",
        "submission-failed,failed": "submit_status == 1 OR run_status == 1",
        "running": "time_run IS NOT NULL AND run_status IS NULL",
        "running,succeeded,failed": "time_run IS NOT NULL",
        "succeeded": "run_status == 0",
        "succeeded,failed": "run_status IS NOT NULL",
        "failed": "run_status == 1",
    }
    REC_CYCLE_QUERY_OP = re.compile(r"\A(before |after |[<>]=?)(.+)\Z")
    REC_SEQ_LOG = re.compile(r"\A(.+\.)([^\.]+)(\.[^\.]+)\Z")

    def __init__(self):
        self.daos = {}

    def _db_init(self, user_name, suite_name):
        """Initialise a named CylcSuiteDAO database connection."""
        key = (user_name, suite_name)
        if key not in self.daos:
            prefix = "~"
            if user_name:
                prefix += user_name
            for name in [os.path.join("log", "db"), "cylc-suite.db"]:
                db_f_name = os.path.expanduser(os.path.join(
                    prefix, os.path.join("cylc-run", suite_name, name)))
                self.daos[key] = CylcSuiteDAO(db_f_name)
                if os.path.exists(db_f_name):
                    break
        return self.daos[key]

    def _db_close(self, user_name, suite_name):
        """Close a named CylcSuiteDAO database connection."""
        key = (user_name, suite_name)
        if self.daos.get(key) is not None:
            self.daos[key].close()

    def _db_exec(self, user_name, suite_name, stmt, stmt_args=None):
        """Execute a query on a named CylcSuiteDAO database connection."""
        daos = self._db_init(user_name, suite_name)
        if stmt_args is None:
            stmt_args = []
        return daos.connect().execute(stmt, stmt_args)

    def get_suite_broadcast_states(self, user_name, suite_name):
        """Return broadcast states of a suite.
        [[point, name, key, value], ...]
        """
        stmt = CylcSuiteDAO.pre_select_broadcast_states(
            self._db_init(user_name, suite_name), order="ASC")[0]
        broadcast_states = []
        for row in self._db_exec(user_name, suite_name, stmt):
            point, namespace, key, value = row
            broadcast_states.append([point, namespace, key, value])
        return broadcast_states

    def get_suite_broadcast_events(self, user_name, suite_name):
        """Return broadcast events of a suite.
        [[time, change, point, name, key, value], ...]
        """
        stmt = CylcSuiteDAO.pre_select_broadcast_events(
            self._db_init(user_name, suite_name), order="DESC")[0]
        broadcast_events = []
        for row in self._db_exec(user_name, suite_name, stmt):
            time_, change, point, namespace, key, value = row
            broadcast_events.append(
                (time_, change, point, namespace, key, value))
        return broadcast_events

    def get_suite_job_entries(
            self, user_name, suite_name, cycles, tasks, task_status,
            job_status, order, limit, offset):
        """Query suite runtime databsae to return a listing of task jobs.
        user -- A string containing a valid user ID
        suite -- A string containing a valid suite ID
        cycles -- If specified, display only task jobs matching these cycles.
                  A value in the list can be a cycle, the string "before|after
                  CYCLE", or a glob to match cycles.
        tasks -- If specified, display only jobs with task names matching
                 these names. Values can be a valid task name or a glob like
                 pattern for matching valid task names.
        task_status -- If specified, it should be a list of task statuses.
                       Display only jobs in the specified list. If not
                       specified, display all jobs.
        job_status -- If specified, must be a string matching a key in
                      CylcReviewDAO.JOB_STATUS_COMBOS. Select jobs by their
                      statuses.
        order -- Order search in a predetermined way. A valid value is one of
                 the keys in CylcReviewDAO.ORDERS.
        limit -- Limit number of returned entries
        offset -- Offset entry number
        Return (entries, of_n_entries) where:
        entries -- A list of matching entries
        of_n_entries -- Total number of entries matching query
        Each entry is a dict:
            {"cycle": cycle, "name": name, "submit_num": submit_num,
             "events": [time_submit, time_init, time_exit],
             "task_status": task_status,
             "logs": {"script": {"path": path, "path_in_tar", path_in_tar,
                                 "size": size, "mtime": mtime},
                      "out": {...},
                      "err": {...},
                      ...}}
        """
        where_expr, where_args = self._get_suite_job_entries_where(
            cycles, tasks, task_status, job_status)

        # Get number of entries
        of_n_entries = 0
        stmt = ("SELECT COUNT(*)" +
                " FROM task_jobs JOIN task_states USING (name, cycle)" +
                where_expr)
        for row in self._db_exec(user_name, suite_name, stmt, where_args):
            of_n_entries = row[0]
            break
        else:
            self._db_close(user_name, suite_name)
            return ([], 0)

        # Get entries
        entries = []
        entry_of = {}
        stmt = ("SELECT" +
                " task_states.time_updated AS time," +
                " cycle, name," +
                " task_jobs.submit_num AS submit_num," +
                " task_states.submit_num AS submit_num_max," +
                " task_states.status AS task_status," +
                " time_submit, submit_status," +
                " time_run, time_run_exit, run_signal, run_status," +
                " user_at_host, batch_sys_name, batch_sys_job_id" +
                " FROM task_jobs JOIN task_states USING (cycle, name)" +
                where_expr +
                " ORDER BY " +
                "time DESC, submit_num DESC, name DESC, cycle DESC")
        limit_args = []
        if limit:
            stmt += " LIMIT ? OFFSET ?"
            limit_args = [limit, offset]
        for row in self._db_exec(
                user_name, suite_name, stmt, where_args + limit_args):
            (
                cycle, name, submit_num, submit_num_max, task_status,
                time_submit, submit_status,
                time_run, time_run_exit, run_signal, run_status,
                user_at_host, batch_sys_name, batch_sys_job_id
            ) = row[1:]
            entry = {
                "cycle": cycle,
                "name": name,
                "submit_num": submit_num,
                "submit_num_max": submit_num_max,
                "events": [time_submit, time_run, time_run_exit],
                "task_status": task_status,
                "submit_status": submit_status,
                "run_signal": run_signal,
                "run_status": run_status,
                "host": user_at_host,
                "submit_method": batch_sys_name,
                "submit_method_id": batch_sys_job_id,
                "logs": {},
                "seq_logs_indexes": {}}
            entries.append(entry)
            entry_of[(cycle, name, submit_num)] = entry
        self._db_close(user_name, suite_name)
        if entries:
            self._get_job_logs(user_name, suite_name, entries, entry_of)
        return (entries, of_n_entries)

    def _get_suite_job_entries_where(
            self, cycles, tasks, task_status, job_status):
        """Helper for get_suite_job_entries.
        Get query's "WHERE" expression and its arguments.
        """
        where_exprs = []
        where_args = []
        if cycles:
            cycle_where_exprs = []
            for cycle in cycles:
                match = self.REC_CYCLE_QUERY_OP.match(cycle)
                if match:
                    operator, operand = match.groups()
                    where_args.append(operand)
                    if operator == "before ":
                        cycle_where_exprs.append("cycle <= ?")
                    elif operator == "after ":
                        cycle_where_exprs.append("cycle >= ?")
                    else:
                        cycle_where_exprs.append("cycle %s ?" % operator)
                else:
                    where_args.append(cycle)
                    cycle_where_exprs.append("cycle GLOB ?")
            where_exprs.append(" OR ".join(cycle_where_exprs))
        if tasks:
            where_exprs.append(" OR ".join(["name GLOB ?"] * len(tasks)))
            where_args += tasks
        if task_status:
            task_status_where_exprs = []
            for item in task_status:
                task_status_where_exprs.append("task_states.status == ?")
                where_args.append(item)
            where_exprs.append(" OR ".join(task_status_where_exprs))
        try:
            job_status_where = self.JOB_STATUS_COMBOS[job_status]
        except KeyError:
            pass
        else:
            if job_status_where:
                where_exprs.append(job_status_where)
        if where_exprs:
            return (" WHERE (" + ") AND (".join(where_exprs) + ")", where_args)
        else:
            return ("", where_args)

    def _get_job_logs(self, user_name, suite_name, entries, entry_of):
        """Helper for "get_suite_job_entries". Get job logs.
        Recent job logs are likely to be in the file system, so we can get a
        listing of the relevant "log/job/CYCLE/NAME/SUBMI_NUM/" directory.
        Older job logs may be archived in "log/job-CYCLE.tar.gz", we should
        only open each relevant TAR file once to obtain a listing for all
        relevant entries of that cycle.
        Modify each entry in entries.
        """
        prefix = "~"
        if user_name:
            prefix += user_name
        user_suite_dir = os.path.expanduser(os.path.join(
            prefix, os.path.join("cylc-run", suite_name)))
        try:
            fs_log_cycles = os.listdir(
                os.path.join(user_suite_dir, "log", "job"))
        except OSError:
            fs_log_cycles = []
        targzip_log_cycles = []
        for name in glob(os.path.join(user_suite_dir, "log", "job-*.tar.gz")):
            targzip_log_cycles.append(os.path.basename(name)[4:-7])

        relevant_targzip_log_cycles = []
        for entry in entries:
            if entry["cycle"] in fs_log_cycles:
                pathd = "log/job/%(cycle)s/%(name)s/%(submit_num)02d" % entry
                try:
                    filenames = os.listdir(os.path.join(user_suite_dir, pathd))
                except OSError:
                    continue
                for filename in filenames:
                    try:
                        stat = os.stat(
                            os.path.join(user_suite_dir, pathd, filename))
                    except OSError:
                        pass
                    else:
                        entry["logs"][filename] = {
                            "path": "/".join([pathd, filename]),
                            "path_in_tar": None,
                            "mtime": int(stat.st_mtime),  # int precise enough
                            "size": stat.st_size,
                            "exists": True,
                            "seq_key": None}
                        continue
            if entry["cycle"] in targzip_log_cycles:
                if entry["cycle"] not in relevant_targzip_log_cycles:
                    relevant_targzip_log_cycles.append(entry["cycle"])

        for cycle in relevant_targzip_log_cycles:
            path = os.path.join("log", "job-%s.tar.gz" % cycle)
            tar = tarfile.open(os.path.join(user_suite_dir, path), "r:gz")
            for member in tar.getmembers():
                # member.name expected to be "job/cycle/task/submit_num/*"
                if not member.isfile():
                    continue
                try:
                    cycle_str, name, submit_num_str = (
                        member.name.split("/", 4)[1:4])
                    entry = entry_of[(cycle_str, name, int(submit_num_str))]
                except (KeyError, ValueError):
                    continue
                entry["logs"][os.path.basename(member.name)] = {
                    "path": path,
                    "path_in_tar": member.name,
                    "mtime": int(member.mtime),  # too precise otherwise
                    "size": member.size,
                    "exists": True,
                    "seq_key": None}

        # Sequential logs
        for entry in entries:
            for filename, filename_items in entry["logs"].items():
                seq_log_match = self.REC_SEQ_LOG.match(filename)
                if not seq_log_match:
                    continue
                head, index_str, tail = seq_log_match.groups()
                seq_key = head + "*" + tail
                filename_items["seq_key"] = seq_key
                if seq_key not in entry["seq_logs_indexes"]:
                    entry["seq_logs_indexes"][seq_key] = {}
                entry["seq_logs_indexes"][seq_key][index_str] = filename
            for seq_key, indexes in entry["seq_logs_indexes"].items():
                # Only one item, not a sequence
                if len(indexes) <= 1:
                    entry["seq_logs_indexes"].pop(seq_key)
                # All index_str are numbers, convert key to integer so
                # the template can sort them as numbers
                try:
                    int_indexes = {}
                    for index_str, filename in indexes.items():
                        int_indexes[int(index_str)] = filename
                    entry["seq_logs_indexes"][seq_key] = int_indexes
                except ValueError:
                    pass
            for filename, log_dict in entry["logs"].items():
                # Unset seq_key for singular items
                if log_dict["seq_key"] not in entry["seq_logs_indexes"]:
                    log_dict["seq_key"] = None

    def get_suite_cycles_summary(
            self, user_name, suite_name, order, limit, offset):
        """Return a the state summary (of each cycle) of a user's suite.
        user -- A string containing a valid user ID
        suite -- A string containing a valid suite ID
        limit -- Limit number of returned entries
        offset -- Offset entry number
        Return (entries, of_n_entries), where entries is a data structure that
        looks like:
            [   {   "cycle": cycle,
                    "n_states": {
                        "active": N, "success": M, "fail": L, "job_fails": K,
                    },
                    "max_time_updated": T2,
                },
                # ...
            ]
        where:
        * cycle is a date-time cycle label
        * N, M, L, K are the numbers of tasks in given states
        * T2 is the time when last update time of (a task in) the cycle
        and of_n_entries is the total number of entries.
        """
        of_n_entries = 0
        stmt = ("SELECT COUNT(DISTINCT cycle) FROM task_states WHERE " +
                "submit_num > 0")
        for row in self._db_exec(user_name, suite_name, stmt):
            of_n_entries = row[0]
            break
        if not of_n_entries:
            return ([], 0)

        # Not strictly correct, if cycle is in basic date-only format,
        # but should not matter for most cases
        integer_mode = False
        stmt = "SELECT cycle FROM task_states LIMIT 1"
        for row in self._db_exec(user_name, suite_name, stmt):
            integer_mode = row[0].isdigit()
            break

        prefix = "~"
        if user_name:
            prefix += user_name
        user_suite_dir = os.path.expanduser(os.path.join(
            prefix, os.path.join("cylc-run", suite_name)))
        targzip_log_cycles = []
        try:
            for item in os.listdir(os.path.join(user_suite_dir, "log")):
                if item.startswith("job-") and item.endswith(".tar.gz"):
                    targzip_log_cycles.append(item[4:-7])
        except OSError:
            pass

        states_stmt = {}
        for key, names in TASK_STATUS_GROUPS.items():
            states_stmt[key] = " OR ".join(
                ["status=='%s'" % (name) for name in names])
        stmt = (
            "SELECT" +
            " cycle," +
            " max(time_updated)," +
            " sum(" + states_stmt["active"] + ") AS n_active," +
            " sum(" + states_stmt["success"] + ") AS n_success,"
            " sum(" + states_stmt["fail"] + ") AS n_fail"
            " FROM task_states" +
            " GROUP BY cycle")
        if integer_mode:
            stmt += " ORDER BY cast(cycle as number)"
        else:
            stmt += " ORDER BY cycle"
        stmt += " DESC"  # ordering choice
        stmt_args = []
        if limit:
            stmt += " LIMIT ? OFFSET ?"
            stmt_args += [limit, offset]
        entry_of = {}
        entries = []
        for row in self._db_exec(user_name, suite_name, stmt, stmt_args):
            cycle, max_time_updated, n_active, n_success, n_fail = row
            if n_active or n_success or n_fail:
                entry_of[cycle] = {
                    "cycle": cycle,
                    "has_log_job_tar_gz": cycle in targzip_log_cycles,
                    "max_time_updated": max_time_updated,
                    "n_states": {
                        "active": n_active,
                        "success": n_success,
                        "fail": n_fail,
                        "job_active": 0,
                        "job_success": 0,
                        "job_fail": 0,
                    },
                }
                entries.append(entry_of[cycle])

        # Check if "task_jobs" table is available or not.
        # Note: A single query with a JOIN is probably a more elegant solution.
        # However, timing tests suggest that it is cheaper with 2 queries.
        # This 2nd query may return more results than is necessary, but should
        # be a very cheap query as it does not have to do a lot of work.
        check_stmt = "SELECT name FROM sqlite_master WHERE name==?"
        check_query = self._db_exec(user_name, suite_name, check_stmt,
                                    ["task_jobs"])
        if check_query.fetchone() is not None:
            stmt = (
                "SELECT cycle," +
                " sum(" + self.JOB_STATUS_COMBOS["submitted,running"] +
                ") AS n_job_active," +
                " sum(" + self.JOB_STATUS_COMBOS["succeeded"] +
                ") AS n_job_success," +
                " sum(" + self.JOB_STATUS_COMBOS["submission-failed,failed"] +
                ") AS n_job_fail" +
                " FROM task_jobs GROUP BY cycle")
        else:
            fail_events_stmt = " OR ".join(
                ["event=='%s'" % (name)
                 for name in TASK_STATUS_GROUPS["fail"]])
            stmt = (
                "SELECT cycle," +
                " sum(" + fail_events_stmt + ") AS n_job_fail" +
                " FROM task_events GROUP BY cycle")
        for cycle, n_job_active, n_job_success, n_job_fail in self._db_exec(
                user_name, suite_name, stmt):
            try:
                entry_of[cycle]["n_states"]["job_active"] = n_job_active
                entry_of[cycle]["n_states"]["job_success"] = n_job_success
                entry_of[cycle]["n_states"]["job_fail"] = n_job_fail
            except KeyError:
                pass
            else:
                del entry_of[cycle]
                if not entry_of:
                    break
        self._db_close(user_name, suite_name)

        return entries, of_n_entries

    def get_suite_state_summary(self, user_name, suite_name):
        """Return a the state summary of a user's suite.
        Return {"is_running": b, "is_failed": b, "server": s}
        where:
        * is_running is a boolean to indicate if the suite is running
        * is_failed: a boolean to indicate if any tasks (submit) failed
        * server: host:port of server, if available
        """
        ret = {
            "is_running": False,
            "is_failed": False,
            "server": None}
        dao = self._db_init(user_name, suite_name)
        if not os.access(dao.db_file_name, os.F_OK | os.R_OK):
            return ret

        port_file_path = os.path.expanduser(
            os.path.join(
                "~" + user_name, "cylc-run", suite_name, ".service",
                "contact"))
        try:
            host = None
            port_str = None
            for line in open(port_file_path):
                key, value = [item.strip() for item in line.split("=", 1)]
                if key == "CYLC_SUITE_HOST":
                    host = value
                elif key == "CYLC_SUITE_PORT":
                    port_str = value
        except (IOError, ValueError):
            pass
        else:
            if host and port_str:
                ret["is_running"] = True
                ret["server"] = host.split(".", 1)[0] + ":" + port_str

        stmt = "SELECT status FROM task_states WHERE status GLOB ? LIMIT 1"
        stmt_args = ["*failed"]
        for _ in self._db_exec(user_name, suite_name, stmt, stmt_args):
            ret["is_failed"] = True
            break
        self._db_close(user_name, suite_name)

        return ret
