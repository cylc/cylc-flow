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

    def get_update_stmt(self, set_args, where_args=None):
        """Return an update statement and its args to update a row.

        return (stmt, stmt_args)

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
        return stmt, stmt_args

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
    """Data access object for a suite runtime database."""

    CONN_TIMEOUT = 0.2
    DB_FILE_BASE_NAME = "cylc-suite.db"
    MAX_TRIES = 100
    TABLE_BROADCASTS = "broadcasts"
    TABLE_TASK_JOBS = "task_jobs"
    TABLE_TASK_EVENTS = "task_events"
    TABLE_TASK_STATES = "task_states"

    def __init__(self, db_file_name=None, is_public=False):
        """Initialise object.

        db_file_name - Path to the database file
        is_public - If True, allow retries, etc

        """
        self.db_file_name = db_file_name
        self.is_public = is_public
        self.conn = None
        self.n_tries = 0

        self.tables = {
            self.TABLE_BROADCASTS: CylcSuiteDAOTable(self.TABLE_BROADCASTS, [
                ["time"],
                ["change"],
                ["point"],
                ["namespace"],
                ["key"],
                ["value"],
            ]),
            self.TABLE_TASK_JOBS: CylcSuiteDAOTable(self.TABLE_TASK_JOBS, [
                ["cycle"],
                ["name"],
                ["submit_num", {"datatype": "INTEGER"}],
                ["is_manual_submit", {"datatype": "INTEGER"}],
                ["try_num", {"datatype": "INTEGER"}],
                ["time_submit"],
                ["time_submit_exit"],
                ["submit_status"],
                ["time_run"],
                ["time_run_exit"],
                ["run_signal"],
                ["run_status"],
                ["user_at_host"],
                ["batch_sys_name"],
                ["batch_sys_job_id"],
            ]),
            self.TABLE_TASK_EVENTS: CylcSuiteDAOTable(self.TABLE_TASK_EVENTS, [
                ["name"],
                ["cycle"],
                ["time"],
                ["submit_num", {"datatype": "INTEGER"}],
                ["event"],
                ["message"],
                ["misc"],
            ]),
            self.TABLE_TASK_STATES: CylcSuiteDAOTable(self.TABLE_TASK_STATES, [
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
            ]),
        }

        if not self.is_public:
            self.connect()
            self.conn.execute("VACUUM")
            self.create_tables()

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
            self.conn.close()
            self.conn = None

    def connect(self):
        """Connect to the database."""
        self.conn = sqlite3.connect(self.db_file_name, self.CONN_TIMEOUT)
        return self.conn

    def create_tables(self):
        """Create tables."""
        self.connect()
        names = []
        for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type==? ORDER BY name",
                ["table"]):
            names.append(row[0])
        for name, table in self.tables.items():
            if name not in names:
                self.conn.execute(table.get_create_stmt())
                self.conn.commit()

    def execute_queued_items(self):
        """Execute queued items for each table."""
        self.connect()
        will_retry = False
        for table in self.tables.values():
            # INSERT statements are uniform for each table, so all INSERT
            # statements can be executed using a single "executemany" call.
            if table.insert_queue:
                try:
                    stmt = table.get_insert_stmt()
                    self.conn.executemany(stmt, table.insert_queue)
                    self.conn.commit()
                except sqlite3.Error as exc:
                    if not self.is_public:
                        raise
                    self.conn.rollback()
                    will_retry = True
                    if cylc.flags.debug:
                        traceback.print_exc()
                        sys.stderr.write(
                            "WARNING: %(file)s: %(table)s: %(stmt)s\n" % {
                                "file": self.db_file_name,
                                "table": table.name,
                                "stmt": stmt})
                        for stmt_args in table.insert_queue:
                            sys.stderr.write(
                                "\t%(stmt_args)s\n" % {"stmt_args": stmt_args})
                    # Not safe to do UPDATE if INSERT failed
                    continue
                else:
                    table.insert_queue = []
            # UPDATE statements can be used to update any fields in many rows
            # so we can only executemany for each identical template statement.
            for stmt, stmt_args_list in table.update_queues.items():
                try:
                    self.conn.executemany(stmt, stmt_args_list)
                    self.conn.commit()
                except sqlite3.Error as exc:
                    if not self.is_public:
                        raise
                    self.conn.rollback()
                    will_retry = True
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
                else:
                    table.update_queues.pop(stmt)
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
