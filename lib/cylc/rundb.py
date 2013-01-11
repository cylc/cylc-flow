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


class UpdateObject(object):
    """UpdateObject for using in tasks"""
    def __init__(self, table, name, cycle, submit_num, **kwargs):
        """Update a row in a table."""
        kwargs["time_updated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        s_fmt = "UPDATE %(table)s SET %(cols)s WHERE name==? AND cycle==? AND submit_num==?"
        cols = ""
        args = []
        not_first = False
        for k, v in kwargs.items():
            if not_first:
                cols += ", "
            not_first = True
            cols += k + "=?"
            args.append(v)
        args.append(name)
        args.append(cycle)
        args.append(submit_num)
        self.s_fmt = s_fmt % {"table": table, "cols": cols}
        self.args = args
        self.to_run = True

class RecordEventObject(object):
    """RecordEventObject for using in tasks"""
    def __init__(self, name, cycle, submit_num, event=None, message=None):
        """Records an event in the table"""
        self.s_fmt = "INSERT INTO task_events VALUES(?, ?, ?, ?, ?, ?)"
        self.args = [name, cycle, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), submit_num, event, message]
        self.to_run = True


class RecordStateObject(object):
    """RecordEventObject for using in tasks"""
    def __init__(self, name, cycle, time_created=datetime.now(), time_updated=None,
                     submit_num=None, is_manual_submit=None, try_num=None,
                     host=None, submit_method=None, submit_method_id=None,
                     status=None):
        """Insert a new row into the states table"""
        self.s_fmt = "INSERT INTO task_states VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        if time_updated is not None:
            time_updated = time_updated.strftime("%Y-%m-%dT%H:%M:%S")
        self.args = [name, cycle, time_created.strftime("%Y-%m-%dT%H:%M:%S"), 
                     time_updated, submit_num, is_manual_submit, try_num, host,
                     submit_method, submit_method_id, status]
        self.to_run = True


class CylcRuntimeDAO(object):
    """Access object for a Cylc suite runtime database."""

    DB_FILE_BASE_NAME = "cylc-suite.db"
    TASK_EVENTS = "task_events"
    TASK_STATES = "task_states"
    TABLES = {
            TASK_EVENTS: [                      # each task event gets a row
                    "name TEXT",
                    "cycle TEXT",               # current cycle time of the task
                    "time INTEGER",             # actual time
                    "submit_num INTEGER",
                    "event TEXT",
                    "message TEXT"],
            TASK_STATES: [                      # each task gets a status entry that is updated
                    "name TEXT",
                    "cycle TEXT",
                    "time_created TEXT",        # actual serverside time
                    "time_updated TEXT",        # actual serverside time
                    "submit_num INTEGER",       # included in key to track status of different submissions for a task
                    "is_manual_submit INTEGER", # boolean - user related or auto?
                    "try_num INTEGER",          # auto-resubmit generates this
                    "host TEXT",                # host for the task
                    "submit_method TEXT",       # to be taken from loadleveller id/process - empty at the moment
                    "submit_method_id TEXT",    # empty at the moment
                    "status TEXT",
                    # TODO: "rc TEXT",
                    # TODO: "auth_key TEXT",
                    ]}
    PRIMARY_KEY_OF = {TASK_EVENTS: None,
                      TASK_STATES: "name, cycle, submit_num"}


    def __init__(self, suite_dir=None, new_mode=False):
        if suite_dir is None:
            suite_dir = os.getcwd()
        self.db_file_name = os.path.join(suite_dir, self.DB_FILE_BASE_NAME)
        if new_mode:
            if os.path.isdir(self.db_file_name):
                shutil.rmtree(self.db_file_name)
            else:
                try:
                    os.unlink(self.db_file_name)
                except:
                    pass
        if not os.path.exists(self.db_file_name):
            new_mode = True
        self.conn = sqlite3.connect(self.db_file_name)
        if new_mode:
            self.create()

    def connect(self):
        self.conn = sqlite3.connect(self.db_file_name)
        return self.conn.cursor()

    def create(self):
        """Create the database tables."""
        c = self.connect()
        for table, cols in self.TABLES.items():
            s = "CREATE TABLE " + table + "("
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

    def record_event(self, name, cycle, submit_num, event=None, message=None):
        """Insert a row to the events table"""
        s_fmt = "INSERT INTO task_events VALUES(?, ?, ?, ?, ?, ?)"
        args = [name, cycle, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), submit_num, event, message]
        c = self.connect()
        c.execute(s_fmt, args)
        self.conn.commit()

    def record_state(self, name, cycle, time_created=datetime.now(), time_updated=None,
                     submit_num=None, is_manual_submit=None, try_num=None,
                     host=None, submit_method=None, submit_method_id=None,
                     status=None):
        """Insert a new row into the states table"""
        s_fmt = "INSERT INTO task_states VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        if time_updated is not None:
            time_updated = time_updated.strftime("%Y-%m-%dT%H:%M:%S")
        args = [name, cycle, time_created.strftime("%Y-%m-%dT%H:%M:%S"), time_updated, submit_num, 
                is_manual_submit, try_num, host, submit_method, 
                submit_method_id, status]
        c = self.connect()
        c.execute(s_fmt, args)
        self.conn.commit()

    def get_task_submit_num(self, name, cycle):
        s_fmt = "SELECT COUNT(*) FROM task_events WHERE name==? AND cycle==? AND event==?"
        args = [name, cycle, "submitted"]
        c = self.connect()
        c.execute(s_fmt, args)
        count = c.fetchone()[0]
        self.conn.commit()
        submit_num = count + 1 #submission numbers should start at 0
        return submit_num
    
    def get_task_current_submit_num(self, name, cycle):
        s_fmt = "SELECT COUNT(*) FROM task_events WHERE name==? AND cycle==? AND event==?"
        args = [name, cycle, "submitted"]
        c = self.connect()
        c.execute(s_fmt, args)
        count = c.fetchone()[0]
        self.conn.commit()
        return count
    
    def update(self, table, name, cycle, submit_num, **kwargs):
        """Update a row in a table."""
        kwargs["time_updated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        s_fmt = "UPDATE %(table)s SET %(cols)s WHERE name==? AND cycle==? AND submit_num==?"
        cols = ""
        args = []
        not_first = False
        for k, v in kwargs.items():
            if not_first:
                cols += ", "
            not_first = True
            cols += k + "=?"
            args.append(v)
        args.append(name)
        args.append(cycle)
        args.append(submit_num)
        c = self.connect()
        c.execute(s_fmt % {"table": table, "cols": cols}, args)
        self.conn.commit()

    def run_db_op(self, db_oper):
        c = self.connect()
        c.execute(db_oper.s_fmt, db_oper.args)
        self.conn.commit()

