#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

import errno
import json
import os
import sqlite3
import sys
from cylc.rundb import CylcSuiteDAO
from cylc.task_state import (
    TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED, TASK_STATUS_FAILED,
    TASK_STATUS_RETRYING)


class CylcSuiteDBChecker(object):
    """Object for querying a suite database"""
    STATE_ALIASES = {
        'finish': [TASK_STATUS_FAILED, TASK_STATUS_SUCCEEDED],
        'start': [
            TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED, TASK_STATUS_FAILED,
            TASK_STATUS_RETRYING],
        'submit': [
            TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_RETRYING,
            TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED, TASK_STATUS_FAILED,
            TASK_STATUS_RETRYING],
        'fail': [TASK_STATUS_FAILED],
        'succeed': [TASK_STATUS_SUCCEEDED],
    }

    def __init__(self, rund, suite):
        db_path = os.path.join(
            os.path.expanduser(rund), suite, "log",
            CylcSuiteDAO.DB_FILE_BASE_NAME)
        if not os.path.exists(db_path):
            raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), db_path)
        self.conn = sqlite3.connect(db_path, timeout=10.0)

    @staticmethod
    def display_maps(res):
        if not res:
            sys.stderr.write("INFO: No results to display.\n")
        else:
            for row in res:
                sys.stdout.write((", ").join(row) + "\n")

    def get_remote_point_format(self):
        """Query a remote suite database for a 'cycle point format' entry"""
        for row in self.conn.execute(
                r"SELECT value FROM " + CylcSuiteDAO.TABLE_SUITE_PARAMS +
                r" WHERE key==?",
                ['cycle_point_format']):
            return row[0]

    def state_lookup(self, state):
        """allows for multiple states to be searched via a status alias"""
        if state in self.STATE_ALIASES:
            return self.STATE_ALIASES[state]
        else:
            return [state]

    def suite_state_query(
            self, task, cycle, status=None, message=None, mask=None):
        """run a query on the suite database"""
        stmt_args = []
        stmt_wheres = []

        if mask is None:
            mask = "name, cycle, status"

        if message:
            target_table = CylcSuiteDAO.TABLE_TASK_OUTPUTS
            mask = "outputs"
        else:
            target_table = CylcSuiteDAO.TABLE_TASK_STATES

        stmt = "select {0} from {1}".format(mask, target_table)
        if task is not None:
            stmt_wheres.append("name==?")
            stmt_args.append(task)
        if cycle is not None:
            stmt_wheres.append("cycle==?")
            stmt_args.append(cycle)

        if status:
            stmt_frags = []
            for state in self.state_lookup(status):
                stmt_args.append(state)
                stmt_frags.append("status==?")
            stmt_wheres.append("(" + (" OR ").join(stmt_frags) + ")")
        if stmt_wheres:
            stmt += " where " + (" AND ").join(stmt_wheres)

        res = []
        for row in self.conn.execute(stmt, stmt_args):
            if not all(v is None for v in row):
                res.append(list(row))

        return res

    def task_state_getter(self, task, cycle):
        """used to get the state of a particular task at a particular cycle"""
        return self.suite_state_query(task, cycle, mask="status")[0]

    def task_state_met(self, task, cycle, status=None, message=None):
        """used to check if a task is in a particular state"""
        res = self.suite_state_query(task, cycle, status, message)
        if status:
            return bool(res)
        elif message:
            for outputs_str, in res:
                for value in json.loads(outputs_str).values():
                    if message == value:
                        return True
            return False

    @staticmethod
    def validate_mask(mask):
        fieldnames = ["name", "status", "cycle"]  # extract from rundb.py?
        for term in mask.split(","):
            if term.strip(" ") not in fieldnames:
                return False
        return True
