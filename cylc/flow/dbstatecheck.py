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

import errno
import json
import os
import sqlite3
import sys
from textwrap import dedent

from cylc.flow.pathutil import expand_path
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.task_state import (
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED
)


class CylcWorkflowDBChecker:
    """Object for querying a workflow database."""
    STATE_ALIASES = {
        'finish': [
            TASK_STATUS_FAILED,
            TASK_STATUS_SUCCEEDED
        ],
        'start': [
            TASK_STATUS_RUNNING,
            TASK_STATUS_SUCCEEDED,
            TASK_STATUS_FAILED
        ],
        'submit': [
            TASK_STATUS_SUBMITTED,
            TASK_STATUS_RUNNING,
            TASK_STATUS_SUCCEEDED,
            TASK_STATUS_FAILED
        ],
        'fail': [
            TASK_STATUS_FAILED
        ],
        'succeed': [
            TASK_STATUS_SUCCEEDED
        ],
    }

    def __init__(self, rund, workflow):
        db_path = expand_path(
            rund, workflow, "log", CylcWorkflowDAO.DB_FILE_BASE_NAME
        )
        if not os.path.exists(db_path):
            raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), db_path)
        self.conn = sqlite3.connect(db_path, timeout=10.0)

    @staticmethod
    def display_maps(res):
        if not res:
            sys.stderr.write("INFO: No results to display.\n")
        else:
            for row in res:
                sys.stdout.write((", ").join([str(s) for s in row]) + "\n")

    def get_remote_point_format(self):
        """Query a remote workflow database for a 'cycle point format' entry."""
        for row in self.conn.execute(dedent(
            rf'''
                SELECT
                    value
                FROM
                    {CylcWorkflowDAO.TABLE_WORKFLOW_PARAMS}
                WHERE
                    key==?
            '''),  # nosec (table name is code constant)
            ['cycle_point_format']
        ):
            return row[0]

    def state_lookup(self, state):
        """Allows for multiple states to be searched via a status alias."""
        if state in self.STATE_ALIASES:
            return self.STATE_ALIASES[state]
        else:
            return [state]

    def workflow_state_query(
            self, task, cycle, status=None, message=None, mask=None):
        """Run a query on the workflow database."""
        stmt_args = []
        stmt_wheres = []

        if mask is None:
            mask = "name, cycle, status"

        if message:
            target_table = CylcWorkflowDAO.TABLE_TASK_OUTPUTS
            mask = "outputs"
        else:
            target_table = CylcWorkflowDAO.TABLE_TASK_STATES

        stmt = dedent(rf'''
            SELECT
                {mask}
            FROM
                {target_table}
        ''')  # nosec
        # * mask is hardcoded
        # * target_table is a code constant
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
            stmt += "WHERE\n    " + (" AND ").join(stmt_wheres)
        if status:
            stmt += dedent("""
                ORDER BY
                    submit_num
            """)
        res = []
        for row in self.conn.execute(stmt, stmt_args):
            if not all(v is None for v in row):
                res.append(list(row))
        return res

    def task_state_met(self, task, cycle, status):
        """Check if the latest flow instance of a task is in a given state."""
        # retrieve all flow-instances of cycle/task
        res = self.workflow_state_query(task, cycle)
        if res:
            # only consider the latest isntance
            return (res[-1])[2] == status
        return False

    def task_output_met(self, task, cycle, message):
        """Check if latest flow instance of a task has emitted a message."""
        # TODO - NEED TO ADD submit_num TO THE task_outputs TABLE SO WE CAN
        # TELL WHICH IS THE LATEST FLOW-INSTANCE (like state_met above).
        res = self.workflow_state_query(task, cycle, message=message)
        return any(
            message == value
            for outputs_str, in res
            for value in json.loads(outputs_str)
        )

    @staticmethod
    def validate_mask(mask):
        fieldnames = ["name", "status", "cycle"]  # extract from rundb.py?
        return all(
            term.strip(' ') in fieldnames
            for term in mask.split(',')
        )
