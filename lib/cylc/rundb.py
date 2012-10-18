#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

from datetime import datetime
import os
import shutil
import sqlite3


class CylcRuntimeDAO(object):
    """Access object for a Cylc suite runtime database."""

    DB_FILE_BASE_NAME = "cylc-suite.db"
    TASK_EVENTS = "task_events"
    TASK_STATES = "task_states"
    TABLES = {
            TASK_EVENTS: [
                    "name TEXT",
                    "cycle TEXT",
                    "time INTEGER",
                    "submit_num INTEGER",
                    "event TEXT",
                    "message TEXT"],
            TASK_STATES: [
                    "name TEXT",
                    "cycle TEXT",
                    "time_created TEXT",
                    "time_updated TEXT",
                    "submit_num INTEGER",
                    "is_manual_submit INTEGER", # boolean
                    "try_num INTEGER",
                    "host TEXT",
                    "submit_method TEXT",
                    "submit_method_id TEXT",
                    "status TEXT",
                    # TODO: "rc TEXT",
                    # TODO: "auth_key TEXT",
                    ]}
    PRIMARY_KEY_OF = {TASK_EVENTS: None, TASK_STATES: "name, cycle"}
                            

    def __init__(self, suite_dir=None, new_mode=False):
        if suite_dir is None:
            suite_dir = os.getcwd()
        self.db_file_name = os.path.join(suite_dir, self.DB_FILE_BASE_NAME)
        if new_mode:
            if os.path.isdir(self.db_file_name):
                shutil.rmtree(self.db_file_name)
            else:
                os.unlink(self.db_file_name)
        self.conn = sqlite3.connect(self.db_file_name)
        if new_mode:
            self.create()

    def create(self):
        """Create the database tables."""
        c = self.conn.cursor()
        for key, cols in self.TABLES.items():
            s = "CREATE TABLE " + key + "("
            not_first = False
            for col in cols:
                if not_first:
                    s += ", "
                not_first = True
                s += col
            if self.PRIMARY_KEY_OF[table]:
                s += ", PRIMARY KEY(" + self.PRIMARY_KEY_OF[table] + ")"
            s += ")"
            c.execute(s)
        self.conn.commit()

    def insert(self, table, name, cycle, **kwargs):
        """Insert a row to a table."""
        s_fmt = "INSERT INTO %(table)s VALUES(?, ?, ?%(cols)s)"
        args = [name, cycle, datetime.now()]
        cols = ""
        while len(args) < len(TABLES[table]):
            args.append(None)
            cols += ", ?"
        c = self.conn.cursor()
        c.execute(s_fmt % {"table": table, "cols": cols}, args)
        self.conn.commit()

    def update(self, table, name, cycle, **kwargs):
        """Update a row in a table."""
        kwargs["time_updated"] = datetime.now()
        s_fmt = "UPDATE %(table)s SET %(cols)s WHERE name==? AND cycle==?"
        cols = ""
        args = []
        not_first = False
        for k, v in kwargs.items():
            if not_first:
                cols += ", "
            not_first = True
            cols += k + "=?"
            args.append(v)
        c = self.conn.cursor()
        c.execute(s_fmt % {"table": table, "cols": cols}, args)
        self.conn.commit()
