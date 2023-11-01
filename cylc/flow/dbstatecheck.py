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
from typing import Optional

from cylc.flow.pathutil import expand_path
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.task_state import (
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED
)


class CylcWorkflowDBChecker:
    """Object for querying a workflow database"""
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

    def __init__(self, rund, workflow, db_path=None):
        # (Explicit dp_path arg is to make testing easier).
        if db_path is None:
            # Infer DB path from workflow name and run dir.
            db_path = expand_path(
                rund, workflow, "log", CylcWorkflowDAO.DB_FILE_BASE_NAME
            )
        if not os.path.exists(db_path):
            raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), db_path)
        self.conn = sqlite3.connect(db_path, timeout=10.0)

        # Get workflow point format.
        try:
            self.point_fmt = self._get_pt_fmt()
            self.back_compat_mode = False
        except sqlite3.OperationalError as exc:
            # BACK COMPAT: Cylc 7 DB (see method below).
            try:
                self.point_fmt = self._get_pt_fmt_compat()
                self.back_compat_mode = True
            except sqlite3.OperationalError:
                raise exc  # original error

    @staticmethod
    def display_maps(res):
        if not res:
            sys.stderr.write("INFO: No results to display.\n")
        else:
            for row in res:
                sys.stdout.write((", ").join(row) + "\n")

    def _get_pt_fmt(self):
        """Query a workflow database for a 'cycle point format' entry"""
        for row in self.conn.execute(
            rf'''
                SELECT
                    value
                FROM
                    {CylcWorkflowDAO.TABLE_WORKFLOW_PARAMS}
                WHERE
                    key==?
            ''',  # nosec (table name is code constant)
            ['cycle_point_format']
        ):
            return row[0]

    def _get_pt_fmt_compat(self):
        """Query a Cylc 7 suite database for 'cycle point format'."""
        # BACK COMPAT: Cylc 7 DB
        # Workflows parameters table name change.
        # from:
        #    8.0.x
        # to:
        #    8.1.x
        # remove at:
        #    8.x
        for row in self.conn.execute(
            rf'''
                SELECT
                    value
                FROM
                    {CylcWorkflowDAO.TABLE_SUITE_PARAMS}
                WHERE
                    key==?
            ''',  # nosec (table name is code constant)
            ['cycle_point_format']
        ):
            return row[0]

    def get_point_format(self):
        """Return the cycle point format of this DB."""
        return self.point_fmt

    def state_lookup(self, state):
        """allows for multiple states to be searched via a status alias"""
        if state in self.STATE_ALIASES:
            return self.STATE_ALIASES[state]
        else:
            return [state]

    def workflow_state_query(
        self,
        task: Optional[str] = None,
        cycle: Optional[str] = None,
        status: Optional[str] = None,
        message: Optional[str] = None
    ):
        """Query task status or outputs in workflow database.

        Returns a list of tasks with matching status or output message.

        All args can be None - print the entire task_states table.

        NOTE: the task_states table holds the latest state only, so querying
        (e.g.) submitted will fail for a task that is running or finished.

        Query cycle=2023, status=succeeded:
           [[foo, 2023, succeeded], [bar, 2023, succeeded]]

        Query task=foo, message="file ready":
           [[foo, 2023, "file ready"], [foo, 2024, "file ready"]]

        Query task=foo, point=2023, message="file ready":
           [[foo, 2023, "file ready"]]

        """
        stmt_args = []
        stmt_wheres = []

        if message:
            target_table = CylcWorkflowDAO.TABLE_TASK_OUTPUTS
            mask = "name, cycle, outputs"
        else:
            target_table = CylcWorkflowDAO.TABLE_TASK_STATES
            mask = "name, cycle, status"

        stmt = rf'''
            SELECT
                {mask}
            FROM
                {target_table}
        '''  # nosec
        # * mask is hardcoded
        # * target_table is a code constant

        if task:
            stmt_wheres.append("name==?")
            stmt_args.append(task)

        if cycle:
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

        # Note we can't use "where outputs==message"; because the outputs
        # table holds a serialized string of all received outputs.

        res = []
        for row in self.conn.execute(stmt, stmt_args):
            if row[-1] is not None:
                # (final column - status - can be None in Cylc 7 DBs)
                res.append(list(row))

        if message:
            # Replace res with a task-states like result,
            # [[foo, 2032, message], [foo, 2033, message]]
            if self.back_compat_mode:
                # Cylc 7 DB: list of {label: message}
                res = [
                    [item[0], item[1], message]
                    for item in res
                    if message in json.loads(item[2]).values()
                ]
            else:
                # Cylc 8 DB list of [message]
                res = [
                    [item[0], item[1], message]
                    for item in res
                    if message in json.loads(item[2])
                ]
        return res

    def task_state_met(
        self,
        task: str,
        cycle: str,
        status: Optional[str] = None,
        message: Optional[str] = None
    ):
        """Return True if cycle/task has achieved status or output message.

        Called when polling for a status or output message.
        """
        return bool(
            self.workflow_state_query(task, cycle, status, message)
        )

    @staticmethod
    def validate_mask(mask):
        fieldnames = ["name", "status", "cycle"]  # extract from rundb.py?
        return all(
            term.strip(' ') in fieldnames
            for term in mask.split(',')
        )
