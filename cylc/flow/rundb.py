# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Provide data access object for the suite runtime database."""

import sqlite3
import traceback
from os.path import expandvars

from cylc.flow import LOG
import cylc.flow.flags


class CylcSuiteDAOTableColumn:
    """Represent a column in a table."""

    __slots__ = ('name', 'datatype', 'is_primary_key')

    def __init__(self, name, datatype, is_primary_key):
        self.name = name
        self.datatype = datatype
        self.is_primary_key = is_primary_key


class CylcSuiteDAOTable:
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

        set_args should be a dict, with column keys and values to be set.
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


class CylcSuiteDAO:
    """Data access object for the suite runtime database."""

    CONN_TIMEOUT = 0.2
    DB_FILE_BASE_NAME = "db"
    MAX_TRIES = 100
    RESTART_INCOMPAT_VERSION = "8.0a2"  # Can't restart suite if <= this vers
    TABLE_BROADCAST_EVENTS = "broadcast_events"
    TABLE_BROADCAST_STATES = "broadcast_states"
    TABLE_INHERITANCE = "inheritance"
    TABLE_SUITE_PARAMS = "suite_params"
    TABLE_SUITE_TEMPLATE_VARS = "suite_template_vars"
    TABLE_TASK_JOBS = "task_jobs"
    TABLE_TASK_EVENTS = "task_events"
    TABLE_TASK_ACTION_TIMERS = "task_action_timers"
    TABLE_TASK_LATE_FLAGS = "task_late_flags"
    TABLE_TASK_OUTPUTS = "task_outputs"
    TABLE_TASK_POOL = "task_pool"
    TABLE_TASK_PREREQUISITES = "task_prerequisites"
    TABLE_TASK_STATES = "task_states"
    TABLE_TASK_TIMEOUT_TIMERS = "task_timeout_timers"
    TABLE_XTRIGGERS = "xtriggers"
    TABLE_ABS_OUTPUTS = "absolute_outputs"

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
        TABLE_INHERITANCE: [
            ["namespace", {"is_primary_key": True}],
            ["inheritance"],
        ],
        TABLE_SUITE_PARAMS: [
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
            ["platform_name"],
            ["job_runner_name"],
            ["job_id"],
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
            ["flow_label", {"is_primary_key": True}],
            ["status"],
            ["is_held", {"datatype": "INTEGER"}],
        ],
        TABLE_TASK_PREREQUISITES: [
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["prereq_name", {"is_primary_key": True}],
            ["prereq_cycle", {"is_primary_key": True}],
            ["prereq_output", {"is_primary_key": True}],
            ["satisfied"],
        ],
        TABLE_XTRIGGERS: [
            ["signature", {"is_primary_key": True}],
            ["results"],
        ],
        TABLE_TASK_STATES: [
            ["name", {"is_primary_key": True}],
            ["cycle", {"is_primary_key": True}],
            ["flow_label", {"is_primary_key": True}],
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
        TABLE_ABS_OUTPUTS: [
            ["cycle"],
            ["name"],
            ["output"],
        ],
    }

    def __init__(self, db_file_name, is_public=False):
        """Initialise database access object.

        Args:
            db_file_name (str): Path to the database file.
            is_public (bool): If True, allow retries, etc.

        """
        self.db_file_name = expandvars(db_file_name)
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

        set_args should be a dict, with column keys and values to be set.
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
                table.insert_queue.clear()
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
        # Filter out CYLC_TEMPLATE_VARS which breaks executemany because it's:
        # - a dict
        # - recursive (contains itself!)
        if stmt_args_list and stmt_args_list[0]:
            stmt_args_list = [
                i for i in stmt_args_list if i[0] != 'CYLC_TEMPLATE_VARS'
            ]

        try:
            self.connect()
            self.conn.executemany(stmt, stmt_args_list)
        except sqlite3.Error:
            if not self.is_public:
                raise
            if cylc.flow.flags.debug:
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

    def pre_select_broadcast_states(self, order=None):
        """Query statement and args formation for select_broadcast_states."""
        form_stmt = r"SELECT point,namespace,key,value FROM %s"
        if order == "ASC":
            ordering = " ORDER BY point ASC, namespace ASC, key ASC"
            form_stmt = form_stmt + ordering
        return form_stmt % self.TABLE_BROADCAST_STATES

    def select_broadcast_states(self, callback, sort=None):
        """Select from broadcast_states.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [point, namespace, key, value]
        """
        stmt = self.pre_select_broadcast_states(order=sort)
        for row_idx, row in enumerate(self.connect().execute(stmt)):
            callback(row_idx, list(row))

    def select_suite_params(self, callback):
        """Select from suite_params.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [key, value]

        E.g. a row might be ['UTC mode', '1']
        """
        stmt = f"SELECT key, value FROM {self.TABLE_SUITE_PARAMS}"
        for row_idx, row in enumerate(self.connect().execute(stmt)):
            callback(row_idx, list(row))

    def select_suite_params_restart_count(self):
        """Return number of restarts in suite_params table."""
        stmt = f"""
            SELECT value FROM {self.TABLE_SUITE_PARAMS}
            WHERE key == 'n_restart';
        """
        result = self.connect().execute(stmt).fetchone()
        return int(result[0]) if result else 0

    def select_suite_template_vars(self, callback):
        """Select from suite_template_vars.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [key,value]
        """
        for row_idx, row in enumerate(self.connect().execute(
                r"SELECT key,value FROM %s" % self.TABLE_SUITE_TEMPLATE_VARS)):
            callback(row_idx, list(row))

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

    def select_task_job(self, cycle, name, submit_num=None):
        """Select items from task_jobs by (cycle, name, submit_num).

        :return: a dict for mapping keys to the column values
        :rtype: dict
        """
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

    def select_jobs_for_restart(self, callback):
        """Select from task_pool+task_states+task_jobs for restart.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [cycle, name, status, submit_num, time_submit, time_run,
             time_run_exit, job_runner_name, job_id, platform_name]
        """
        form_stmt = r"""
            SELECT
                %(task_pool)s.cycle,
                %(task_pool)s.name,
                %(task_pool)s.status,
                %(task_states)s.submit_num,
                %(task_jobs)s.time_submit,
                %(task_jobs)s.time_run,
                %(task_jobs)s.time_run_exit,
                %(task_jobs)s.job_runner_name,
                %(task_jobs)s.job_id,
                %(task_jobs)s.platform_name
            FROM
                %(task_jobs)s
            JOIN
                %(task_pool)s
            ON  %(task_jobs)s.cycle == %(task_pool)s.cycle AND
                %(task_jobs)s.name == %(task_pool)s.name
            JOIN
                %(task_states)s
            ON  %(task_jobs)s.cycle == %(task_states)s.cycle AND
                %(task_jobs)s.name == %(task_states)s.name AND
                %(task_jobs)s.submit_num == %(task_states)s.submit_num
        """
        form_data = {
            "task_pool": self.TABLE_TASK_POOL,
            "task_states": self.TABLE_TASK_STATES,
            "task_jobs": self.TABLE_TASK_JOBS,
        }
        stmt = form_stmt % form_data
        for row_idx, row in enumerate(self.connect().execute(stmt)):
            callback(row_idx, list(row))

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

    def select_task_job_platforms(self):
        """Return the set of platform names from task_jobs table."""
        stmt = f"SELECT DISTINCT platform_name FROM {self.TABLE_TASK_JOBS}"
        return set(i[0] for i in self.connect().execute(stmt))

    def select_submit_nums(self, name, point):
        """Select submit_num and flow_label from task_states table.

        Fetch submit number and flow label for spawning task name.point.
        Return:
        {
            flow_label: submit_num,
            ...,
        }

        Args:
            name: task name
            point: task cycle point (str)
        """
        # Ignore bandit false positive: B608: hardcoded_sql_expressions
        # Not an injection, simply putting the table name in the SQL query
        # expression as a string constant local to this module.
        stmt = (  # nosec
            r"SELECT flow_label,submit_num FROM %(name)s"
            r" WHERE name==? AND cycle==?"
        ) % {"name": self.TABLE_TASK_STATES}
        ret = {}
        for flow_label, submit_num in self.connect().execute(
                stmt, (name, point,)):
            ret[flow_label] = submit_num
        return ret

    def select_xtriggers_for_restart(self, callback):
        stm = r"SELECT signature,results FROM %s" % self.TABLE_XTRIGGERS
        for row_idx, row in enumerate(self.connect().execute(stm, [])):
            callback(row_idx, list(row))

    def select_abs_outputs_for_restart(self, callback):
        stm = r"SELECT cycle,name,output FROM %s" % self.TABLE_ABS_OUTPUTS
        for row_idx, row in enumerate(self.connect().execute(stm, [])):
            callback(row_idx, list(row))

    def select_task_pool(self, callback):
        """Select from task_pool.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [cycle, name, status]
        """
        form_stmt = r"SELECT cycle,name,status,is_held FROM %s"
        stmt = form_stmt % self.TABLE_TASK_POOL
        for row_idx, row in enumerate(self.connect().execute(stmt)):
            callback(row_idx, list(row))

    def select_task_pool_for_restart(self, callback):
        """Select from task_pool+task_states+task_jobs for restart.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [cycle, name, is_late, status, is_held, submit_num,
             try_num, platform_name, time_submit, time_run, timeout, outputs]
        """
        form_stmt = r"""
            SELECT
                %(task_pool)s.cycle,
                %(task_pool)s.name,
                %(task_pool)s.flow_label,
                %(task_late_flags)s.value,
                %(task_pool)s.status,
                %(task_pool)s.is_held,
                %(task_states)s.submit_num,
                %(task_jobs)s.try_num,
                %(task_jobs)s.platform_name,
                %(task_jobs)s.time_submit,
                %(task_jobs)s.time_run,
                %(task_timeout_timers)s.timeout,
                %(task_outputs)s.outputs
            FROM
                %(task_pool)s
            JOIN
                %(task_states)s
            ON  %(task_pool)s.cycle == %(task_states)s.cycle AND
                %(task_pool)s.name == %(task_states)s.name AND
                %(task_pool)s.flow_label == %(task_states)s.flow_label
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
        stmt = form_stmt % form_data
        for row_idx, row in enumerate(self.connect().execute(stmt)):
            callback(row_idx, list(row))

    def select_task_prerequisites(self, cycle, name):
        """Return prerequisites of a task of the given name & cycle point."""
        stmt = f"""
            SELECT
                prereq_name,
                prereq_cycle,
                prereq_output,
                satisfied
            FROM
                {self.TABLE_TASK_PREREQUISITES}
            WHERE
                cycle == '{cycle}' AND
                name == '{name}'
        """
        return list(self.connect().execute(stmt))

    def select_task_times(self):
        """Select submit/start/stop times to compute job timings.

        To make data interpretation easier, choose the most recent succeeded
        task to sample timings from.
        """
        q = """
            SELECT
                name,
                cycle,
                platform_name,
                job_runner_name,
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
            'name', 'cycle', 'host', 'job_runner',
            'submit_time', 'start_time', 'succeed_time'
        )
        return columns, [r for r in self.connect().execute(q)]

    def vacuum(self):
        """Vacuum to the database."""
        return self.connect().execute("VACUUM")

    def remove_columns(self, table, to_drop):
        conn = self.connect()

        # get list of columns to keep
        schema = conn.execute(
            rf'''
                PRAGMA table_info({table})
            '''
        )
        new_cols = [
            name
            for _, name, *_ in schema
            if name not in to_drop
        ]

        # copy table
        conn.execute(
            rf'''
                CREATE TABLE {table}_new AS
                SELECT {', '.join(new_cols)}
                FROM {table}
            '''
        )

        # remove original
        conn.execute(
            rf'''
                DROP TABLE {table}
            '''
        )

        # copy table
        conn.execute(
            rf'''
                CREATE TABLE {table} AS
                SELECT {', '.join(new_cols)}
                FROM {table}_new
            '''
        )

        # done
        conn.commit()
