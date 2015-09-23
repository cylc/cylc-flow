#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

from logging import getLogger, WARNING
import sqlite3
import sys
import traceback
import cylc.flags


class CylcSuiteDAOTableColumn(object):
    """Represent a column in a table."""

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
    DB_FILE_BASE_NAME = "cylc-suite.db"
    MAX_TRIES = 100
    TABLE_BROADCAST_EVENTS = "broadcast_events"
    TABLE_BROADCAST_STATES = "broadcast_states"
    TABLE_TASK_JOBS = "task_jobs"
    TABLE_TASK_JOB_LOGS = "task_job_logs"
    TABLE_TASK_EVENTS = "task_events"
    TABLE_TASK_STATES = "task_states"

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
        TABLE_TASK_JOB_LOGS: [
            ["cycle", {"is_primary_key": True}],
            ["name", {"is_primary_key": True}],
            ["submit_num", {"datatype": "INTEGER", "is_primary_key": True}],
            ["filename", {"is_primary_key": True}],
            ["location"],
            ["mtime"],
            ["size", {"datatype": "INTEGER"}],
        ],
        TABLE_TASK_EVENTS: [
            ["name"],
            ["cycle"],
            ["time"],
            ["submit_num", {"datatype": "INTEGER"}],
            ["event"],
            ["message"],
            ["misc"],
        ],
        TABLE_TASK_STATES: [
            ["name", {"is_primary_key": True}],
            ["cycle", {"is_primary_key": True}],
            ["time_created"],
            ["time_updated"],
            ["submit_num", {"datatype": "INTEGER"}],
            ["is_manual_submit", {"datatype": "INTEGER"}],
            ["try_num", {"datatype": "INTEGER"}],
            ["host"],
            ["submit_method"],
            ["submit_method_id"],
            ["status"],
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
            except sqlite3.Error as exc:
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
        for name, table in self.tables.items():
            if name not in names:
                self.conn.execute(table.get_create_stmt())
                self.conn.commit()

    def execute_queued_items(self):
        """Execute queued items for each table."""
        will_retry = False
        for table in self.tables.values():
            # DELETE statements may have varying number of WHERE args
            # so we can only executemany for each identical template statement.
            for stmt, stmt_args_list in table.delete_queues.items():
                self.connect()
                if self._execute_stmt(table, stmt, stmt_args_list):
                    table.delete_queues.pop(stmt)
                else:
                    will_retry = True
            # INSERT statements are uniform for each table, so all INSERT
            # statements can be executed using a single "executemany" call.
            if table.insert_queue:
                self.connect()
                if self._execute_stmt(
                        table, table.get_insert_stmt(), table.insert_queue):
                    table.insert_queue = []
                else:
                    will_retry = True
            # UPDATE statements can have varying number of SET and WHERE args
            # so we can only executemany for each identical template statement.
            for stmt, stmt_args_list in table.update_queues.items():
                self.connect()
                if self._execute_stmt(table, stmt, stmt_args_list):
                    table.update_queues.pop(stmt)
                else:
                    will_retry = True
        if self.conn is not None:
            try:
                self.conn.commit()
            except sqlite3.Error:
                if not self.is_public:
                    raise 
                self.conn.rollback()
                if cylc.flags.debug:
                    traceback.print_exc()
                    sys.stderr.write(
                        "WARNING: %s: db commit failed\n" % self.db_file_name)
                will_retry = True
        
        if will_retry:
            self.n_tries += 1
            logger = getLogger("main")
            logger.log(
                WARNING,
                "%(file)s: write attempt (%(attempt)d) did not complete\n" % {
                    "file": self.db_file_name, "attempt": self.n_tries})
        else:
            if self.n_tries:
                logger = getLogger("main")
                logger.log(
                    WARNING,
                    "%(file)s: recovered after (%(attempt)d) attempt(s)\n" % {
                        "file": self.db_file_name, "attempt": self.n_tries})
            self.n_tries = 0

        # N.B. This is not strictly necessary. However, if the suite run
        # directory is removed, a forced reconnection to the private database
        # will ensure that the suite dies.
        self.close()

    def _execute_stmt(self, table, stmt, stmt_args_list):
        """Helper for "self.execute_queued_items".

        Execute a statement. If this is the public database, return True on
        success and False on failure. If this is the private database, return
        True on success, and raise on failure.
        """
        try:
            self.conn.executemany(stmt, stmt_args_list)
        except sqlite3.Error:
            if not self.is_public:
                raise
            if cylc.flags.debug:
                traceback.print_exc()
                sys.stderr.write(
                    "WARNING: %(file)s: %(table)s: %(stmt)s\n" % {
                        "file": self.db_file_name,
                        "table": table.name,
                        "stmt": stmt})
                for stmt_args in stmt_args_list:
                    sys.stderr.write("\t%(stmt_args)s\n" % {
                        "stmt_args": stmt_args})
            return False
        else:
            return True

    def select_task_job(self, keys, cycle, name, submit_num=None):
        """Select items from task_jobs by (cycle, name, submit_num).

        Return a dict for mapping keys to the column values.

        """
        if keys is None:
            keys = []
            for column in self.tables[self.TABLE_TASK_JOBS].columns[3:]:
                keys.append(column.name)
        if submit_num in [None, "NN"]:
            stmt = (r"SELECT %(keys_str)s FROM %(table)s" +
                    r" WHERE cycle==? AND name==?" +
                    r" ORDER BY submit_num DESC LIMIT 1") % {
                "keys_str": ",".join(keys),
                "table": self.TABLE_TASK_JOBS}
            stmt_args = [cycle, name]
        else:
            stmt = (r"SELECT %(keys_str)s FROM %(table)s" +
                    r" WHERE cycle==? AND name==? AND submit_num==?") % {
                "keys_str": ",".join(keys),
                "table": self.TABLE_TASK_JOBS}
            stmt_args = [cycle, name, submit_num]
        ret = {}
        for row in self.connect().execute(stmt, stmt_args):
            ret = {}
            for key, value in zip(keys, row):
                ret[key] = value
            return ret

    def select_task_states_by_task_ids(self, keys, task_ids=None):
        """Select items from task_states by task IDs.

        Return a data structure like this:

        {
            (name1, point1): {key1: "value 1", ...},
            ...,
        }

        task_ids should be specified as [[name, cycle], ...]

        """
        if keys is None:
            keys = []
            for column in self.tables[self.TABLE_TASK_STATES].columns[2:]:
                keys.append(column.name)
        stmt = r"SELECT name,cycle,%(keys_str)s FROM %(name)s" % {
            "keys_str": ",".join(keys),
            "name": self.TABLE_TASK_STATES}
        stmt_args = []
        if task_ids:
            stmt += (
                " WHERE (" +
                ") OR (".join(["name==? AND cycle==?"] * len(task_ids)) +
                ")")
            for name, cycle in task_ids:
                stmt_args += [name, cycle]
        ret = {}
        for row in self.connect().execute(stmt, stmt_args):
            name, cycle = row[0:2]
            ret[(name, cycle)] = {}
            for key, value in zip(keys, row[2:]):
                ret[(name, cycle)][key] = value
        return ret

    def select_task_states_by_cycles(self, keys, cycles=None):
        """Select items from task_states by cycles.

        Return a data structure like this:

        {
            (name1, point1): {key1: "value 1", ...},
            ...,
        }

        cycles should be a list of relevant cycles.

        """
        stmt = r"SELECT name,cycle,%(keys_str)s FROM %(name)s" % {
            "keys_str": ",".join(keys),
            "name": self.TABLE_TASK_STATES}
        stmt_args = []
        if cycles:
            stmt += " WHERE " + " OR ".join(["cycle==?"] * len(cycles))
            stmt_args += [str(cycle) for cycle in cycles]
        ret = {}
        for row in self.connect().execute(stmt, stmt_args):
            name, cycle = row[0:2]
            ret[(name, cycle)] = {}
            for key, value in zip(keys, row[2:]):
                ret[(name, cycle)][key] = value
        return ret

    def vacuum(self):
        """Vacuum to the database."""
        return self.connect().execute("VACUUM")
