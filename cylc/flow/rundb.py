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
"""Provide data access object for the workflow runtime database."""

from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass
from os.path import expandvars
from pprint import pformat
import sqlite3
import traceback
from typing import (
    TYPE_CHECKING,
    Any,
    DefaultDict,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

from cylc.flow import LOG
from cylc.flow.exceptions import PlatformLookupError
import cylc.flow.flags
from cylc.flow.flow_mgr import stringify_flow_nums
from cylc.flow.util import (
    deserialise_set,
    serialise_set,
)


if TYPE_CHECKING:
    from pathlib import Path

    from cylc.flow.flow_mgr import FlowNums


DbArgDict = Dict[str, Any]
DbUpdateTuple = Union[
    Tuple[DbArgDict, DbArgDict],
    Tuple[str, list]
]


@dataclass
class CylcWorkflowDAOTableColumn:
    """Represent a column in a table."""

    name: str
    datatype: str
    is_primary_key: bool


class CylcWorkflowDAOTable:
    """Represent a table in the workflow runtime database."""

    FMT_CREATE = "CREATE TABLE %(name)s(%(columns_str)s%(primary_keys_str)s)"
    FMT_DELETE = "DELETE FROM %(name)s%(where_str)s"
    FMT_INSERT = "INSERT OR REPLACE INTO %(name)s VALUES(%(values_str)s)"
    FMT_UPDATE = "UPDATE %(name)s SET %(set_str)s%(where_str)s"

    __slots__ = ('name', 'columns', 'delete_queues', 'insert_queue',
                 'update_queues')

    def __init__(self, name, column_items):
        self.name = name
        self.columns: List[CylcWorkflowDAOTableColumn] = []
        for column_item in column_items:
            name = column_item[0]
            attrs = {}
            if len(column_item) > 1:
                attrs = column_item[1]
            self.columns.append(CylcWorkflowDAOTableColumn(
                name,
                attrs.get("datatype", "TEXT"),
                attrs.get("is_primary_key", False)))
        self.delete_queues = {}
        self.insert_queue = []
        self.update_queues: DefaultDict[str, list] = defaultdict(list)

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

    def add_update_item(self, item: DbUpdateTuple) -> None:
        """Queue an UPDATE item.

        If stmt is not a string, it should be a tuple (set_args, where_args) -
        set_args should be a dict, with column keys and values to be set.
        where_args should be a dict, update will only apply to rows matching
        all these items.

        """
        if isinstance(item[0], str):
            stmt = item[0]
            params = cast('list', item[1])
            self.update_queues[stmt].extend(params)
            return

        set_args = item[0]
        where_args = cast('DbArgDict', item[1])
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
            "where_str": where_str
        }
        self.update_queues[stmt].append(stmt_args)


class CylcWorkflowDAO:
    """Data access object for the workflow runtime database."""

    CONN_TIMEOUT = 0.2
    DB_FILE_BASE_NAME = "db"
    MAX_TRIES = 100
    RESTART_INCOMPAT_VERSION = "8.0rc2"  # Can't restart if <= this version
    TABLE_BROADCAST_EVENTS = "broadcast_events"
    TABLE_BROADCAST_STATES = "broadcast_states"
    TABLE_INHERITANCE = "inheritance"
    TABLE_WORKFLOW_PARAMS = "workflow_params"
    # BACK COMPAT: suite_params
    # This Cylc 7 DB table is needed to allow workflow-state
    # xtriggers (and the `cylc workflow-state` command) to
    # work with Cylc 7 workflows.
    # url: https://github.com/cylc/cylc-flow/issues/5236
    # remove at: 8.x
    TABLE_SUITE_PARAMS = "suite_params"
    TABLE_WORKFLOW_FLOWS = "workflow_flows"
    TABLE_WORKFLOW_TEMPLATE_VARS = "workflow_template_vars"
    TABLE_TASK_JOBS = "task_jobs"
    TABLE_TASK_EVENTS = "task_events"
    TABLE_TASK_ACTION_TIMERS = "task_action_timers"
    TABLE_TASK_LATE_FLAGS = "task_late_flags"
    TABLE_TASK_OUTPUTS = "task_outputs"
    TABLE_TASK_POOL = "task_pool"
    TABLE_TASK_PREREQUISITES = "task_prerequisites"
    TABLE_TASK_STATES = "task_states"
    TABLE_TASK_TIMEOUT_TIMERS = "task_timeout_timers"
    TABLE_TASKS_TO_HOLD = "tasks_to_hold"
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
        TABLE_WORKFLOW_PARAMS: [
            ["key", {"is_primary_key": True}],
            ["value"],
        ],
        TABLE_WORKFLOW_FLOWS: [
            ["flow_num", {"datatype": "INTEGER", "is_primary_key": True}],
            ["start_time"],
            ["description"],
        ],
        TABLE_WORKFLOW_TEMPLATE_VARS: [
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
        # NOTE: this table is used by `cylc clean`, don't rename me!
        TABLE_TASK_JOBS: [
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["submit_num", {"datatype": "INTEGER", "is_primary_key": True}],
            ["flow_nums"],
            ["is_manual_submit", {"datatype": "INTEGER"}],
            ["try_num", {"datatype": "INTEGER"}],
            # This is used to store simulation task start time across restarts.
            ["time_submit"],
            ["time_submit_exit"],
            ["submit_status", {"datatype": "INTEGER"}],
            ["time_run"],
            ["time_run_exit"],
            ["run_signal"],
            ["run_status", {"datatype": "INTEGER"}],
            # NOTE: this field is used by `cylc clean` don't rename me!
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
            ["flow_nums", {"is_primary_key": True}],
            ["outputs"],
        ],
        TABLE_TASK_POOL: [
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["flow_nums", {"is_primary_key": True}],
            ["status"],
            ["is_held", {"datatype": "INTEGER"}],
        ],
        TABLE_TASK_PREREQUISITES: [
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["flow_nums", {"is_primary_key": True}],
            ["prereq_name", {"is_primary_key": True}],
            ["prereq_cycle", {"is_primary_key": True}],
            ["prereq_output", {"is_primary_key": True}],
            ["satisfied"],
        ],
        # The xtriggers table holds the function signature and result of
        # already-satisfied (the scheduler no longer needs to call them).
        TABLE_XTRIGGERS: [
            ["signature", {"is_primary_key": True}],
            ["results"],
        ],
        TABLE_TASK_STATES: [
            ["name", {"is_primary_key": True}],
            ["cycle", {"is_primary_key": True}],
            ["flow_nums", {"is_primary_key": True}],
            ["time_created"],
            ["time_updated"],
            ["submit_num", {"datatype": "INTEGER"}],
            ["status"],
            ["flow_wait", {"datatype": "INTEGER"}],
            ["is_manual_submit", {"datatype": "INTEGER"}],
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
        TABLE_TASKS_TO_HOLD: [
            ["name"],
            ["cycle"],
        ],
    }

    def __init__(
        self,
        db_file_name: Union['Path', str],
        is_public: bool = False,
        create_tables: bool = False
    ):
        """Initialise database access object.

        An instance of this class can also be opened as a context manager
        which will automatically close the DB connection.

        Args:
            db_file_name: Path to the database file.
            is_public: If True, allow retries.
            create_tables: If True, create the tables if they
                don't already exist.

        """
        self.db_file_name = expandvars(db_file_name)
        self.is_public = is_public
        self.conn: Optional[sqlite3.Connection] = None
        self.n_tries = 0

        self.tables = {
            name: CylcWorkflowDAOTable(name, attrs)
            for name, attrs in sorted(self.TABLES_ATTRS.items())
        }

        if create_tables:
            self.create_tables()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Close DB connection when leaving context manager."""
        self.close()

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

    def add_update_item(
        self, table_name: str, item: DbUpdateTuple
    ) -> None:
        """Queue an UPDATE item for a given table.

        If stmt is not a string, it should be a tuple (set_args, where_args) -
        set_args should be a dict, with column keys and values to be set.
        where_args should be a dict, update will only apply to rows matching
        all these items.

        """
        self.tables[table_name].add_update_item(item)

    def close(self) -> None:
        """Explicitly close the connection."""
        if self.conn is not None:
            try:
                self.conn.close()
            except sqlite3.Error as exc:
                LOG.debug(f"Error closing connection to DB: {exc}")
            self.conn = None

    def connect(self) -> sqlite3.Connection:
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
        # determine the sql statements to execute
        sql_queue = []  # (sql_statement, values)
        for table in self.tables.values():
            # DELETE statements may have varying number of WHERE args so we
            # can only executemany for each identical template statement.
            for stmt, stmt_args_list in table.delete_queues.items():
                sql_queue.append((stmt, stmt_args_list))

            # INSERT statements are uniform for each table, so all INSERT
            # statements can be executed using a single "executemany" call.
            if table.insert_queue:
                sql_queue.append((
                    table.get_insert_stmt(),
                    table.insert_queue,
                ))

            # UPDATE statements can have varying number of SET and WHERE
            # args so we can only executemany for each identical template
            # statement.
            for stmt, stmt_args_list in table.update_queues.items():
                sql_queue.append((stmt, stmt_args_list))

        # execute the statements and commit the transaction
        try:
            for stmt, stmt_args in sql_queue:
                self._execute_stmt(stmt, stmt_args)
            # Connection should only be opened if we have executed something.
            if self.conn is None:
                return
            self.conn.commit()

        # something went wrong
        # (includes DB file not found, transaction processing issue, db locked)
        except sqlite3.Error as e:
            if not self.is_public:
                # incase this isn't a filesystem issue, log the statements
                # which make up the transaction to assist debug
                LOG.error(
                    'An error occurred when writing to the database,'
                    ' this is probably a filesystem issue.'
                    f' The attempted transaction was:\n{pformat(sql_queue)}'
                )
                raise
            self.n_tries += 1
            LOG.warning(
                "%(file)s: write attempt (%(attempt)d)"
                " did not complete: %(error)s\n" % {
                    "file": self.db_file_name,
                    "attempt": self.n_tries,
                    "error": str(e)
                }
            )
            if self.conn is not None:
                with suppress(sqlite3.Error):
                    self.conn.rollback()
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
            # Note: This is not strictly necessary. But if the workflow run
            # directory is removed, a forced reconnection to the private
            # database will ensure that the workflow dies.
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
            if cylc.flow.flags.verbosity > 1:
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

    def select_workflow_params(self) -> Iterable[Tuple[str, Optional[str]]]:
        """Select all from workflow_params.

        E.g. a row might be ('UTC mode', '1')
        """
        stmt = rf'''
            SELECT
                key, value
            FROM
                {self.TABLE_WORKFLOW_PARAMS}
        '''  # nosec B608 (table name is code constant)
        return self.connect().execute(stmt)

    def select_workflow_flows(self, flow_nums: Iterable[int]):
        """Return flow data for selected flows."""
        stmt = rf'''
            SELECT
                flow_num, start_time, description
            FROM
                {self.TABLE_WORKFLOW_FLOWS}
            WHERE
                flow_num in ({stringify_flow_nums(flow_nums)})
        '''  # nosec B608 (table name is code constant, flow_nums just ints)
        flows = {}
        for flow_num, start_time, descr in self.connect().execute(stmt):
            flows[flow_num] = {
                "start_time": start_time,
                "description": descr
            }
        return flows

    def select_workflow_flows_max_flow_num(self):
        """Return max flow number in the workflow_flows table."""
        stmt = rf'''
            SELECT
                MAX(flow_num)
            FROM
                {self.TABLE_WORKFLOW_FLOWS}
        '''  # nosec B608 (table name is code constant)
        return self.connect().execute(stmt).fetchone()[0]

    def select_workflow_params_restart_count(self):
        """Return number of restarts in workflow_params table."""
        stmt = rf"""
            SELECT
                value
            FROM
                {self.TABLE_WORKFLOW_PARAMS}
            WHERE
                key == 'n_restart'
        """  # nosec B608 (table name is code constant)
        result = self.connect().execute(stmt).fetchone()
        return int(result[0]) if result else 0

    def select_workflow_template_vars(self, callback):
        """Select from workflow_template_vars.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [key,value]
        """
        for row_idx, row in enumerate(self.connect().execute(
                rf'''
                    SELECT
                        key, value
                    FROM
                        {self.TABLE_WORKFLOW_TEMPLATE_VARS}
                '''  # nosec B608 (table name is code constant)
        )):
            callback(row_idx, list(row))

    def select_task_action_timers(self, callback):
        """Select from task_action_timers for restart.

        Invoke callback(row_idx, row) on each row.
        """
        attrs = []
        for item in self.TABLES_ATTRS[self.TABLE_TASK_ACTION_TIMERS]:
            attrs.append(item[0])
        stmt = rf'''
            SELECT
                {",".join(attrs)}
            FROM
                {self.TABLE_TASK_ACTION_TIMERS}
        '''  # nosec B608
        # * table name is code constant
        # * attrs are code constants
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
            stmt = rf'''
                SELECT
                    {",".join(keys)}
                FROM
                    {self.TABLE_TASK_JOBS}
                WHERE
                    cycle==?
                    AND name==?
                ORDER BY
                    submit_num DESC LIMIT 1
            '''  # nosec B608
            # * table name is code constant
            # * keys are code constants
            stmt_args = [cycle, name]
        else:
            stmt = rf'''
                SELECT
                    {",".join(keys)}
                FROM
                    {self.TABLE_TASK_JOBS}
                WHERE
                    cycle==?
                    AND name==?
                    AND submit_num==?
            '''  # nosec B608
            # * table name is code constant
            # * keys are code constants
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

        Invoke callback(row_idx, row) on each row of the result.
        """
        form_stmt = r"""
            SELECT
                %(task_pool)s.cycle,
                %(task_pool)s.name,
                %(task_jobs)s.submit_num,
                %(task_jobs)s.time_submit,
                %(task_jobs)s.submit_status,
                %(task_jobs)s.time_run,
                %(task_jobs)s.time_run_exit,
                %(task_jobs)s.run_status,
                %(task_jobs)s.job_runner_name,
                %(task_jobs)s.job_id,
                %(task_jobs)s.platform_name
            FROM
                %(task_jobs)s
            JOIN
                %(task_pool)s
            ON  %(task_jobs)s.cycle == %(task_pool)s.cycle AND
                %(task_jobs)s.name == %(task_pool)s.name
        """
        form_data = {
            "task_pool": self.TABLE_TASK_POOL,
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
        """Return the set of platform names from task_jobs table.

        Warning:
            This interface is used by `cylc clean` which does not upgrade the
            DB first (it could, this would only extend backwards
            compatibility but would not help with forwards compatibility).
            Keep this query to the minimum of tables/fields to avoid
            breaking compatibility with older/newer versions of Cylc.

        """
        stmt = rf'''
            SELECT DISTINCT
                platform_name
            FROM
                {self.TABLE_TASK_JOBS}
        '''  # nosec B608 (table name is code constant)
        return {i[0] for i in self.connect().execute(stmt)}

    def select_prev_instances(
        self, name: str, point: str
    ) -> List[Tuple[int, bool, Set[int], str]]:
        """Select task_states table info about previous instances of a task.

        Flow merge results in multiple entries for the same submit number.
        """
        # Ignore bandit false positive: B608: hardcoded_sql_expressions
        # Not an injection, simply putting the table name in the SQL query
        # expression as a string constant local to this module.
        stmt = (  # nosec B608
            r"SELECT flow_nums,submit_num,flow_wait,status FROM %(name)s"
            r" WHERE name==? AND cycle==?"
        ) % {"name": self.TABLE_TASK_STATES}
        return [
            (
                submit_num,
                flow_wait == 1,
                deserialise_set(flow_nums_str),
                status
            )
            for flow_nums_str, submit_num, flow_wait, status in (
                self.connect().execute(stmt, (name, point,))
            )
        ]

    def select_latest_flow_nums(self) -> Optional['FlowNums']:
        """Return a list of the most recent previous flow numbers."""
        stmt = rf'''
            SELECT
                flow_nums, MAX(time_created)
            FROM
                {self.TABLE_TASK_STATES}
            WHERE
                flow_nums != ?
        '''  # nosec B608 (table name is code constant)
        # Exclude flow=none:
        params = [serialise_set()]
        flow_nums_str = self.connect().execute(stmt, params).fetchone()[0]
        if flow_nums_str:
            return deserialise_set(flow_nums_str)
        return None

    def select_task_outputs(
        self, name: str, point: str
    ) -> 'Dict[str, FlowNums]':
        """Select task outputs for each flow.

        Return: {outputs_dict_str: flow_nums_set}

        """
        stmt = rf'''
            SELECT
               flow_nums,outputs
            FROM
               {self.TABLE_TASK_OUTPUTS}
            WHERE
                name==? AND cycle==?
        '''  # nosec B608 (table name is code constant)
        return {
            outputs: deserialise_set(flow_nums)
            for flow_nums, outputs in self.connect().execute(
                stmt, (name, point,)
            )
        }

    def select_xtriggers_for_restart(self, callback):
        stmt = rf'''
            SELECT
                signature, results
            FROM
                {self.TABLE_XTRIGGERS}
        '''  # nosec B608 (table name is code constant)
        for row_idx, row in enumerate(self.connect().execute(stmt, [])):
            callback(row_idx, list(row))

    def select_abs_outputs_for_restart(self, callback):
        stmt = rf'''
            SELECT
                cycle, name, output
            FROM
                {self.TABLE_ABS_OUTPUTS}
        '''  # nosec B608 (table name is code constant)
        for row_idx, row in enumerate(self.connect().execute(stmt, [])):
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
        the fields in the SELECT statement below.

        Raises:
            PlatformLookupError: Do not start up if platforms for running
            tasks cannot be found in global.cylc. This exception should
            not be caught.
        """
        form_stmt = r"""
            SELECT
                %(task_pool)s.cycle,
                %(task_pool)s.name,
                %(task_pool)s.flow_nums,
                %(task_states)s.flow_wait,
                %(task_states)s.is_manual_submit,
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
                %(task_pool)s.flow_nums == %(task_states)s.flow_nums
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
                %(task_pool)s.name == %(task_outputs)s.name AND
                %(task_pool)s.flow_nums == %(task_outputs)s.flow_nums
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

        # Run the callback, collecting any platform errors to be handled later:
        platform_errors = []
        for row_idx, row in enumerate(self.connect().execute(stmt)):
            platform_error = callback(row_idx, list(row))
            if platform_error:
                platform_errors.append(platform_error)

        # If any of the platforms could not be found, raise an exception
        # and stop trying to play this workflow:
        if platform_errors:
            msg = (
                "The following platforms are not defined in"
                " the global.cylc file:"
            )
            for platform in platform_errors:
                msg += f"\n * {platform}"
            raise PlatformLookupError(msg)

    def select_task_prerequisites(
        self, cycle: str, name: str, flow_nums: str
    ) -> List[Tuple[str, str, str, str]]:
        """Return prerequisites of a task of the given name & cycle point."""
        stmt = rf"""
            SELECT
                prereq_name,
                prereq_cycle,
                prereq_output,
                satisfied
            FROM
                {self.TABLE_TASK_PREREQUISITES}
            WHERE
                cycle == ? AND
                name == ? AND
                flow_nums == ?
        """  # nosec B608 (table name is code constant)
        stmt_args = [cycle, name, flow_nums]
        return list(self.connect().execute(stmt, stmt_args))

    def select_tasks_to_hold(self) -> List[Tuple[str, str]]:
        """Return all tasks to hold stored in the DB."""
        stmt = rf'''
            SELECT
                name, cycle
            FROM
                {self.TABLE_TASKS_TO_HOLD}
        '''  # nosec B608 (table name is code constant)
        return list(self.connect().execute(stmt))

    def select_task_times(self):
        """Select submit/start/stop times to compute job timings.

        To make data interpretation easier, choose the most recent succeeded
        task to sample timings from.
        """
        stmt = rf"""
            SELECT
                name,
                cycle,
                platform_name,
                job_runner_name,
                time_submit,
                time_run,
                time_run_exit
            FROM
                {self.TABLE_TASK_JOBS}
            WHERE
                run_status = 0
        """  # nosec B608 (table name is code constant)
        columns = (
            'name', 'cycle', 'host', 'job_runner',
            'submit_time', 'start_time', 'succeed_time'
        )
        return columns, list(self.connect().execute(stmt))

    def select_tasks_for_datastore(
        self, task_ids
    ):
        """Select state and outputs of specified tasks."""
        if not task_ids:
            return []
        form_stmt = r"""
            SELECT
                %(task_states)s.cycle,
                %(task_states)s.name,
                %(task_states)s.flow_nums,
                %(task_states)s.status,
                MAX(%(task_states)s.submit_num),
                %(task_outputs)s.outputs
            FROM
                %(task_states)s
            LEFT OUTER JOIN
                %(task_outputs)s
            ON  %(task_states)s.cycle == %(task_outputs)s.cycle AND
                %(task_states)s.name == %(task_outputs)s.name
            WHERE
                %(task_states)s.cycle || '/' || %(task_states)s.name IN (
                    %(task_ids)s
                )
            GROUP BY
                %(task_states)s.cycle, %(task_states)s.name
        """
        form_data = {
            "task_states": self.TABLE_TASK_STATES,
            "task_outputs": self.TABLE_TASK_OUTPUTS,
            "task_ids": ', '.join(f"'{val}'" for val in task_ids),
        }
        stmt = form_stmt % form_data
        return list(self.connect().execute(stmt))

    def select_prereqs_for_datastore(
        self, prereq_ids
    ):
        """Select prerequisites of specified tasks."""
        if not prereq_ids:
            return []
        form_stmt = r"""
            SELECT
                cycle,
                name,
                prereq_name,
                prereq_cycle,
                prereq_output,
                satisfied
            FROM
                %(prerequisites)s
            WHERE
                cycle || '/' || name || '/' || flow_nums IN (
                    %(prereq_tasks_args)s
                )
        """
        form_data = {
            "prerequisites": self.TABLE_TASK_PREREQUISITES,
            "prereq_tasks_args": ', '.join(f"'{val}'" for val in prereq_ids),
        }
        stmt = form_stmt % form_data
        return list(self.connect().execute(stmt))

    def select_jobs_for_datastore(
        self, task_ids
    ):
        """Select jobs of of specified tasks."""
        if not task_ids:
            return []
        form_stmt = r"""
            SELECT
                %(task_states)s.cycle,
                %(task_states)s.name,
                %(task_jobs)s.submit_num,
                %(task_jobs)s.time_submit,
                %(task_jobs)s.submit_status,
                %(task_jobs)s.time_run,
                %(task_jobs)s.time_run_exit,
                %(task_jobs)s.run_status,
                %(task_jobs)s.job_runner_name,
                %(task_jobs)s.job_id,
                %(task_jobs)s.platform_name
            FROM
                %(task_jobs)s
            JOIN
                %(task_states)s
            ON  %(task_jobs)s.cycle == %(task_states)s.cycle AND
                %(task_jobs)s.name == %(task_states)s.name
            WHERE
                %(task_states)s.cycle || '/' || %(task_states)s.name IN (
                    %(task_ids)s
                )
            ORDER BY
                %(task_states)s.submit_num DESC
        """
        form_data = {
            "task_states": self.TABLE_TASK_STATES,
            "task_jobs": self.TABLE_TASK_JOBS,
            "task_ids": ', '.join(f"'{val}'" for val in task_ids),
        }
        stmt = form_stmt % form_data
        return list(self.connect().execute(stmt))

    def vacuum(self):
        """Vacuum to the database."""
        return self.connect().execute("VACUUM")
