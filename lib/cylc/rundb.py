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

from datetime import datetime
import errno
from time import sleep
import os
import Queue
import shutil
import sqlite3
import stat
import sys
from threading import Thread
from mkdir_p import mkdir_p
from cylc.wallclock import get_current_time_string
import cPickle as pickle


class UpdateObject(object):
    """UpdateObject for using in tasks"""
    def __init__(self, table, name, cycle, **kwargs):
        """Update a row in a table."""
        kwargs["time_updated"] = get_current_time_string()
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


class RecordBroadcastObject(object):
    """RecordBroadcastObject for using in broadcast settings dumps"""
    def __init__(self, time_string, dump_string):
        """Records a dumped string in the broadcast table"""
        self.s_fmt = "INSERT INTO broadcast_settings VALUES(?, ?)"
        self.args = [time_string, dump_string]


class RecordEventObject(object):
    """RecordEventObject for using in tasks"""
    def __init__(self, name, cycle, submit_num, event=None, message=None, misc=None):
        """Records an event in the table"""
        self.s_fmt = "INSERT INTO task_events VALUES(?, ?, ?, ?, ?, ?, ?)"
        self.args = [name, cycle, get_current_time_string(),
                     submit_num, event, message, misc]


class RecordStateObject(object):
    """RecordStateObject for using in tasks"""
    def __init__(self, name, cycle, time_created_string=None,
                 time_updated_string=None, submit_num=None,
                 is_manual_submit=None, try_num=None, host=None,
                 submit_method=None, submit_method_id=None, status=None):
        """Insert a new row into the states table"""
        if time_created_string is None:
            time_created_string = get_current_time_string()
        self.s_fmt = "INSERT INTO task_states VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        self.args = [name, cycle, time_created_string, time_updated_string,
                     submit_num, is_manual_submit, try_num, host,
                     submit_method, submit_method_id, status]


class RecordOutputObject(object):
    """RecordOutputObject for using in tasks"""
    # Recorded outputs need to be distinct from the event record, as resetting
    # task state, e.g. to retrigger a succeeded task, has to reset its outputs.
    def __init__(self, identity, message=None):
        """Insert a new row into the outputs table"""
        self.s_fmt = "INSERT OR REPLACE INTO task_outputs VALUES(?, ?)"
        self.args = [identity, message]


class DeleteOutputObject(object):
    """DeleteOutputObject for using in tasks"""
    def __init__(self, identity, message=None):
        """Delete a row from the outputs table"""
        self.s_fmt = "DELETE FROM task_outputs WHERE identity ==? AND message ==?"
        self.args = [identity, message]


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
    def __init__(self, db, dump, restart=False):
        super(ThreadedCursor, self).__init__()
        self.max_commit_attempts = 5
        self.db=db
        self.db_dump_name = dump
        self.reqs=Queue.Queue()
        self.db_dump_msg = ("[INFO] Dumping database queue (%s items) to: %s")
        self.db_dump_load = ("[INFO] Loading dumped database queue (%s items) from: %s")
        self.integrity_msg = ("Database Integrity Error: %s:\n"+
                              "\tConverting INSERT to INSERT OR REPLACE for:\n"+
                              "\trequest: %s\n\targs: %s")
        self.generic_err_msg = ("%s:%s occurred while trying to run:\n"+
                              "\trequest: %s\n\targs: %s")
        self.db_not_found_err = ("Database Not Found Error:\n"+
                                 "\tNo database found at %s")
        self.retry_warning = ("[WARNING] retrying database operation on %s - retry %s \n"+
                              "\trequest: %s\n\targs: %s")
        if restart:
            self.load_queue()
        self.start()
        self.exception = None


    def run(self):
        cnx = sqlite3.connect(self.db, timeout=10.0)
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
            self.lastreq = req
            self.lastarg = arg
            self.lastbulk = bulk
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
                        # dump database queue - should only be readable by suite owner
                        self.dump_queue()
                        raise Exception(self.generic_err_msg%(type(e),str(e),req,arg))
                    print >> sys.stderr, self.retry_warning%(self.db, str(attempt), req, arg)
                    sleep(1)
                except Exception as e:
                    # Capture all other integrity errors and raise more helpful message
                    attempt += 1
                    if attempt >= self.max_commit_attempts:
                        self.exception = e
                        # dump database queue - should only be readable by suite owner
                        self.dump_queue()
                        raise Exception(self.generic_err_msg%(type(e),str(e),req,arg))
                    print >> sys.stderr, self.retry_warning%(self.db, str(attempt), req, arg)
                    sleep(1)
            counter += 1
        cnx.commit()
        cnx.close()

    def execute(self, req, arg=None, res=None, bulk=False):
        self.reqs.put((req, arg or tuple(), res, bulk))

    def select(self, req, arg=None):
        res=Queue.Queue()
        self.execute(req, arg, res)
        while True:
            rec=res.get()
            if rec=='--no more--': break
            yield rec

    def close(self):
        self.execute('--close--')

    def dump_queue(self):
        """Dump out queued database operations"""
        queue_dump = {}
        if not self.lastreq.startswith("SELECT"):
            queue_dump[0] = {}
            queue_dump[0]['req'] = self.lastreq
            queue_dump[0]['args'] = self.lastarg
            queue_dump[0]['is_bulk'] = self.lastbulk

        i = 1
        while True:
            try:
                req, arg, res, bulk = self.reqs.get_nowait()
            except Queue.Empty:
                break
            # Ignore queries and database close messages
            if not res and not req == "--close--":
                queue_dump[i] = {}
                queue_dump[i]['req'] = req
                queue_dump[i]['args'] = arg
                queue_dump[i]['is_bulk'] = bulk
                i += 1

        print >> sys.stderr, self.db_dump_msg%(len(queue_dump.keys()), str(self.db_dump_name))
        pickle.dump(queue_dump, open(self.db_dump_name, "wb"))

        # Protect the file
        os.chmod(self.db_dump_name, stat.S_IRUSR | stat.S_IWUSR)
        return

    def load_queue(self):
        """Reload queue from a dump"""
        if os.path.exists(self.db_dump_name):
            dumped_queue = pickle.load( open( self.db_dump_name, "rb" ) )
            print >> sys.stdout, self.db_dump_load%(len(dumped_queue.keys()), str(self.db_dump_name))
            for item in dumped_queue.keys():
                self.execute(dumped_queue[item]['req'],
                             dumped_queue[item]['args'],
                             bulk=dumped_queue[item]['is_bulk'])
            os.remove(self.db_dump_name)
        return


class CylcRuntimeDAO(object):
    """Access object for a Cylc suite runtime database."""

    DB_FILE_BASE_NAME = "cylc-suite.db"
    DB_DUMP_BASE_NAME = "cylc_db_dump.p"
    TASK_EVENTS = "task_events"
    TASK_STATES = "task_states"
    TASK_OUTPUTS = "task_outputs"
    BROADCAST_SETTINGS = "broadcast_settings"
    TABLES = {
            TASK_OUTPUTS: [
                    "identity TEXT",
                    "message TEXT"],
            TASK_EVENTS: [                      # each task event gets a row
                    "name TEXT",
                    "cycle TEXT",               # current cycle point of the task
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
                      TASK_OUTPUTS: "identity, message",
                      TASK_STATES: "name, cycle",
                      BROADCAST_SETTINGS: None}


    def __init__(self, suite_dir=None, new_mode=False, primary_db=True):
        if suite_dir is None:
            suite_dir = os.getcwd()
        if primary_db:
            prefix = os.path.join(suite_dir, 'state')
        else:
            prefix = suite_dir

        self.db_file_name = os.path.join(prefix, self.DB_FILE_BASE_NAME)
        self.db_dump_name = os.path.join(prefix, self.DB_DUMP_BASE_NAME)
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
            # Restrict the primary database to user access only
            if primary_db:
                os.chmod(self.db_file_name, stat.S_IRUSR | stat.S_IWUSR)
            # Clear out old db operations dump
            if os.path.exists(self.db_dump_name):
                os.remove(self.db_dump_name)
        else:
            self.lock_check()

        self.c = ThreadedCursor(self.db_file_name, self.db_dump_name, not new_mode)

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

    def lock_check(self):
        """Try to create a dummy table"""
        c = self.connect()
        c.execute("CREATE TABLE lock_check (entry TEXT)")
        c.execute("DROP TABLE lock_check")

    def get_task_submit_num(self, name, cycle):
        s_fmt = ("SELECT COUNT(*) FROM task_events" +
                 " WHERE name==? AND cycle==? AND event==?")
        args = [name, str(cycle), "incrementing submit number"]
        count = 0
        for row in self.c.select(s_fmt, args):
            count = row[0]  # submission numbers should start at 0
            break
        return count + 1

    def get_task_current_submit_num(self, name, cycle):
        s_fmt = ("SELECT COUNT(*) FROM task_events" +
                 " WHERE name==? AND cycle==? AND event==?")
        args = [name, str(cycle), "incrementing submit number"]
        for row in self.c.select(s_fmt, args):
            return row[0]

    def get_task_state_exists(self, name, cycle):
        s_fmt = "SELECT COUNT(*) FROM task_states WHERE name==? AND cycle==?"
        for row in self.c.select(s_fmt, [name, str(cycle)]):
            return row[0] > 0
        return False

    def get_task_host(self, name, cycle):
        """Return the host name for task "name" at a given cycle."""
        s_fmt = r"SELECT host FROM task_states WHERE name==? AND cycle==?"
        for row in self.c.select(s_fmt, [name, str(cycle)]):
            return row[0]

    def get_task_location(self, name, cycle):
        s_fmt = """SELECT misc FROM task_events WHERE name==? AND cycle==?
                   AND event=="submission succeeded" AND misc!=""
                   ORDER BY submit_num DESC LIMIT 1"""
        for row in self.c.select(s_fmt, [name, str(cycle)]):
            return row

    def get_task_submit_method_id_and_try(self, name, cycle):
        s_fmt = """SELECT submit_method_id, try_num FROM task_states WHERE name==? AND cycle==?
                   ORDER BY submit_num DESC LIMIT 1"""
        for row in self.c.select(s_fmt, [name, str(cycle)]):
            return row

    def run_db_op(self, db_oper):
        if not os.path.exists(self.db_file_name):
            raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), self.db_file_name)
        if isinstance(db_oper, BulkDBOperObject):
            self.c.execute(db_oper.s_fmt, db_oper.args, bulk=True)
        else:
            self.c.execute(db_oper.s_fmt, db_oper.args)

    def get_restart_info(self, cycle):
        """Get all the task names and submit count for a particular cycle"""
        s_fmt = """SELECT name FROM task_states WHERE cycle ==?"""
        args = [cycle]
        res = {}
        for row in self.c.select(s_fmt, args):
            res[row[0]] = 0
        
        s_fmt = """SELECT name, count(*) FROM task_events WHERE cycle ==? AND
                   event ==? GROUP BY name"""
        args = [cycle, "incrementing submit number"]
        
        for name, count in self.c.select(s_fmt, args):
            res[name] = count

        return res

    def get_outputs_table(self):
        """Return the entire task outputs table."""

        s_fmt = """SELECT * FROM task_outputs"""
        args = []
        table = {}
        for taskid, msg in self.c.select(s_fmt, args):
            table[str(msg)] = str(taskid)
        return table
