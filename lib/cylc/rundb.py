#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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
from time import sleep
import os
import shutil
import sqlite3
import sys
from threading import Thread
from Queue import Queue
from mkdir_p import mkdir_p

class UpdateObject(object):
    """UpdateObject for using in tasks"""
    def __init__(self, table, name, cycle, **kwargs):
        """Update a row in a table."""
        kwargs["time_updated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
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
        args.append(name)
        args.append(cycle)
        self.s_fmt = s_fmt % {"table": table, "cols": cols}
        self.args = args
        self.to_run = True

class RecordBroadcastObject(object):
    """RecordBroadcastObject for using in broadcast settings dumps"""
    def __init__(self, timestamp, dumpstring):
        """Records a dumped string in the broadcast table"""
        self.s_fmt = "INSERT INTO broadcast_settings VALUES(?, ?)"
        self.args = [timestamp, dumpstring]
        self.to_run = True

class RecordEventObject(object):
    """RecordEventObject for using in tasks"""
    def __init__(self, name, cycle, submit_num, event=None, message=None, misc=None):
        """Records an event in the table"""
        self.s_fmt = "INSERT INTO task_events VALUES(?, ?, ?, ?, ?, ?, ?)"
        self.args = [name, cycle, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                     submit_num, event, message, misc]
        self.to_run = True


class RecordStateObject(object):
    """RecordStateObject for using in tasks"""
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

class BulkDBOperObject(object):
    """BulkDBOperObject for grouping together related operations"""
    def __init__(self, base_object):
        self.s_fmt = base_object.s_fmt
        self.args = []
        self.args.append(base_object.args)
    def add_oper(self, db_object):
        if db_object.s_fmt != self.s_fmt:
            raise Exception( "ERROR: cannot combine different types of database operation" )
        self.args.append(db_object.args)

class ThreadedCursor(Thread):
    def __init__(self, db):
        super(ThreadedCursor, self).__init__()
        self.max_commit_attempts = 5
        self.db=db
        self.reqs=Queue()
        self.start()
        self.exception = None
        self.integrity_msg = ("Database Integrity Error: %s:\n"+
                              "\tConverting INSERT to INSERT OR REPLACE for:\n"+
                              "\trequest: %s\n\targs: %s")
        self.generic_err_msg = ("%s:%s occurred while trying to run:\n"+
                              "\trequest: %s\n\targs: %s")
    def run(self):
        cnx = sqlite3.connect(self.db)
        cursor = cnx.cursor()
        counter = 1
        while True:
            if (counter % 10) == 0 or self.reqs.qsize() == 0:
                counter = 0
                attempt = 0
                while attempt < self.max_commit_attempts:
                    try:
                        cnx.commit()
                        break
                    except Exception as e:
                        attempt += 1
                        if attempt >= self.max_commit_attempts:
                            self.exception = e
                            raise e
                        sleep(1)
            attempt = 0
            req, arg, res, bulk = self.reqs.get()
            if req=='--close--': break
            while attempt < self.max_commit_attempts:
                try:
                    if bulk:
                        cursor.executemany(req, arg)
                    else:
                        cursor.execute(req, arg)
                    if res:
                        for rec in cursor:
                            res.put(rec)
                        res.put('--no more--')
                    cnx.commit()
                    break
                except sqlite3.IntegrityError as e:
                    # Capture integrity errors, refactor request and report to stderr
                    attempt += 1
                    if req.startswith("INSERT INTO"):
                        print >> sys.stderr, self.integrity_msg%(str(e),req,arg)
                        req = req.replace("INSERT INTO", "INSERT OR REPLACE INTO", 1)
                    if attempt >= self.max_commit_attempts:
                        self.exception = e
                        raise Exception(self.generic_err_msg%(type(e),str(e),req,arg))
                    sleep(1)
                except Exception as e:
                    # Capture all other integrity errors and raise more helpful message
                    attempt += 1
                    if attempt >= self.max_commit_attempts:
                        self.exception = e
                        raise Exception(self.generic_err_msg%(type(e),str(e),req,arg))
                    sleep(1)
            counter += 1
        cnx.commit()
        cnx.close()
    def execute(self, req, arg=None, res=None, bulk=False):
        self.reqs.put((req, arg or tuple(), res, bulk))
    def select(self, req, arg=None):
        res=Queue()
        self.execute(req, arg, res)
        while True:
            rec=res.get()
            if rec=='--no more--': break
            yield rec
    def close(self):
        self.execute('--close--')


class CylcRuntimeDAO(object):
    """Access object for a Cylc suite runtime database."""

    DB_FILE_BASE_NAME = "cylc-suite.db"
    TASK_EVENTS = "task_events"
    TASK_STATES = "task_states"
    BROADCAST_SETTINGS = "broadcast_settings"
    TABLES = {
            TASK_EVENTS: [                      # each task event gets a row
                    "name TEXT",
                    "cycle TEXT",               # current cycle time of the task
                    "time INTEGER",             # actual time
                    "submit_num INTEGER",
                    "event TEXT",
                    "message TEXT",
                    "misc TEXT"],               # e.g. record the user@host associated with this event
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
                    ],
            BROADCAST_SETTINGS: [
                    "timestamp TEXT",
                    "broadcast TEXT"
                    ]}
    PRIMARY_KEY_OF = {TASK_EVENTS: None,
                      TASK_STATES: "name, cycle",
                      BROADCAST_SETTINGS: None}


    def __init__(self, suite_dir=None, new_mode=False):
        if suite_dir is None:
            suite_dir = os.getcwd()
        self.db_file_name = os.path.join(suite_dir, self.DB_FILE_BASE_NAME)
        # create the host directory if necessary
        try:
            mkdir_p( suite_dir )
        except Exception, x:
            raise Exception( "ERROR: " + str(x) )

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
        if new_mode:
            self.create()
        self.c = ThreadedCursor(self.db_file_name)

    def close(self):
        self.c.close()

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
            res = c.execute(s)
        return

    def get_task_submit_num(self, name, cycle):
        s_fmt = "SELECT COUNT(*) FROM task_events WHERE name==? AND cycle==? AND event==?"
        args = [name, cycle, "submitting now"]
        count = self.c.select(s_fmt, args).next()[0]
        submit_num = count + 1 #submission numbers should start at 0
        return submit_num

    def get_task_current_submit_num(self, name, cycle):
        s_fmt = "SELECT COUNT(*) FROM task_events WHERE name==? AND cycle==? AND event==?"
        args = [name, cycle, "submitting now"]
        count = self.c.select(s_fmt, args).next()[0]
        return count

    def get_task_state_exists(self, name, cycle):
        s_fmt = "SELECT COUNT(*) FROM task_states WHERE name==? AND cycle==?"
        args = [name, cycle]
        count = self.c.select(s_fmt, args).next()[0]
        return count > 0

    def get_task_host(self, name, cycle):
        """Return the host name for task "name" at a given cycle."""
        s_fmt = r"SELECT host FROM task_states WHERE name==? AND cycle==?"
        for row in self.c.select(s_fmt, [name, cycle]):
            return row[0]

    def get_task_location(self, name, cycle):
        s_fmt = """SELECT misc FROM task_events WHERE name==? AND cycle==?
                   AND event=="submission succeeded" AND misc!=""
                   ORDER BY submit_num DESC LIMIT 1"""
        args = [name, cycle]
        res = self.c.select(s_fmt, args).next()
        return res

    def get_task_sumbit_method_id_and_try(self, name, cycle):
        s_fmt = """SELECT submit_method_id, try_num FROM task_states WHERE name==? AND cycle==?
                   ORDER BY submit_num DESC LIMIT 1"""
        args = [name, cycle]
        res = self.c.select(s_fmt, args).next()
        return res

    def run_db_op(self, db_oper):
        if isinstance(db_oper, BulkDBOperObject):
            self.c.execute(db_oper.s_fmt, db_oper.args, bulk=True)
        else:
            self.c.execute(db_oper.s_fmt, db_oper.args)

