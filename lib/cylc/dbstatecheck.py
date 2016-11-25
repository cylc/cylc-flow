#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

import os
import sqlite3
import sys
from cylc.rundb import CylcSuiteDAO
from cylc.task_state import (
    TASK_STATUS_HELD, TASK_STATUS_WAITING, TASK_STATUS_EXPIRED,
    TASK_STATUS_QUEUED, TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED, TASK_STATUS_RETRYING)


class DBOperationError(Exception):

    """An exception raised on db operation failure, typically due to a lock."""

    def __str__(self):
        return "Suite database operation failed: %s" % self.args


class DBNotFoundError(Exception):

    """An exception raised when a suite database is not found."""

    def __str__(self):
        return "Suite database not found at: %s" % self.args


class CylcSuiteDBChecker(object):
    """Object for querying a suite database"""
    STATE_ALIASES = {}
    STATE_ALIASES['finish'] = [TASK_STATUS_FAILED, TASK_STATUS_SUCCEEDED]
    STATE_ALIASES['start'] = [TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED,
                              TASK_STATUS_FAILED, TASK_STATUS_RETRYING]
    STATE_ALIASES['submit'] = [TASK_STATUS_SUBMITTED,
                               TASK_STATUS_SUBMIT_RETRYING,
                               TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED,
                               TASK_STATUS_FAILED, TASK_STATUS_RETRYING]
    STATE_ALIASES['fail'] = [TASK_STATUS_FAILED]
    STATE_ALIASES['succeed'] = [TASK_STATUS_SUCCEEDED]

    def __init__(self, suite_dir, suite):
        # possible to set suite_dir to system default cylc-run dir?
        suite_dir = os.path.expanduser(suite_dir)
        self.db_address = os.path.join(
            suite_dir, suite, "log", CylcSuiteDAO.DB_FILE_BASE_NAME)
        if not os.path.exists(self.db_address):
            raise DBNotFoundError(self.db_address)
        self.conn = sqlite3.connect(self.db_address, timeout=10.0)
        self.c = self.conn.cursor()

    def display_maps(self, res):
        if not res:
            sys.stderr.write("INFO: No results to display.\n")
        else:
            for row in res:
                sys.stdout.write((", ").join(row).encode("utf-8") + "\n")

    def state_lookup(self, state):
        """allows for multiple states to be searched via a status alias"""
        if state in self.STATE_ALIASES:
            return self.STATE_ALIASES[state]
        else:
            return state

    def suite_state_query(self, task=None, cycle=None, status=None, mask=None):
        """run a query on the suite database"""
        vals = []
        additionals = []
        res = []
        if mask is None:
            mask = "name, cycle, status"
        q_base = "select {0} from task_states".format(mask)
        if task is not None:
            additionals.append("name==?")
            vals.append(task)
        if cycle is not None:
            additionals.append("cycle==?")
            vals.append(cycle)
        if status is not None:
            st = self.state_lookup(status)
            if type(st) is list:
                add = []
                for s in st:
                    vals.append(s)
                    add.append("status==?")
                additionals.append("(" + (" OR ").join(add) + ")")
            else:
                additionals.append("status==?")
                vals.append(status)
        if additionals:
            q = q_base + " where " + (" AND ").join(additionals)
        else:
            q = q_base

        try:
            self.c.execute(q, vals)
            next = self.c.fetchmany()
            while next:
                res.append(next[0])
                next = self.c.fetchmany()
        except sqlite3.OperationalError as err:
            raise DBOperationError(str(err))
        except Exception as err:
            sys.stderr.write("unable to query suite database: " + str(err))
            sys.exit(1)

        return res

    def task_state_getter(self, task, cycle):
        """used to get the state of a particular task at a particular cycle"""
        res = self.suite_state_query(task, cycle, mask="status")
        return res[0]

    def task_state_met(self, task, cycle, status):
        """used to check if a task is in a particular state"""
        res = self.suite_state_query(task, cycle, status)
        return len(res) > 0

    def validate_mask(self, mask):
        fieldnames = ["name", "status", "cycle"]  # extract from rundb.py?
        for term in mask.split(","):
            if term.strip(" ") not in fieldnames:
                return False
        return True
