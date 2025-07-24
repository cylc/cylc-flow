#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Provide data access object for the suite runtime database."""

import sqlite3
import os
import tarfile
import re
from glob import glob
from sqlite3 import OperationalError

from cylc.rundb import CylcSuiteDAO
from cylc.task_state import TASK_STATUS_GROUPS
"""Provide data access object to the suite runtime database for Cylc Review."""


def get_prefix(user_name):
    """Return user "home" dir under $CYLC_REVIEW_HOME, or else ~user_name."""
    if os.environ.get('CYLC_REVIEW_HOME', False) and user_name:
        prefix = os.path.join(
            os.environ['CYLC_REVIEW_HOME'],
            str(user_name)
        )
    else:
        prefix = "~"
        if user_name:
            prefix += user_name
    return prefix


class CylcReviewDAO(object):
    """Cylc Review data access object to the suite runtime database."""

    CYCLE_ORDERS = {"time_desc": " DESC", "time_asc": " ASC"}
    JOB_ORDERS = {
        "time_desc": "time DESC, submit_num DESC, name DESC, cycle DESC",
        "time_asc": "time ASC, submit_num ASC, name ASC, cycle ASC",
        "cycle_desc_name_asc": "cycle DESC, name ASC, submit_num DESC",
        "cycle_desc_name_desc": "cycle DESC, name DESC, submit_num DESC",
        "cycle_asc_name_asc": "cycle ASC, name ASC, submit_num DESC",
        "cycle_asc_name_desc": "cycle ASC, name DESC, submit_num DESC",
        "name_asc_cycle_asc": "name ASC, cycle ASC, submit_num DESC",
        "name_desc_cycle_asc": "name DESC, cycle ASC, submit_num DESC",
        "name_asc_cycle_desc": "name ASC, cycle DESC, submit_num DESC",
        "name_desc_cycle_desc": "name DESC, cycle DESC, submit_num DESC",
        "time_submit_desc": (
            "time_submit DESC, submit_num DESC, name DESC, cycle DESC"),
        "time_submit_asc": (
            "time_submit ASC, submit_num DESC, name DESC, cycle DESC"),
        "time_run_desc": (
            "time_run DESC, submit_num DESC, name DESC, cycle DESC"),
        "time_run_asc": (
            "time_run ASC, submit_num DESC, name DESC, cycle DESC"),
        "time_run_exit_desc": (
            "time_run_exit DESC, submit_num DESC, name DESC, cycle DESC"),
        "time_run_exit_asc": (
            "time_run_exit ASC, submit_num DESC, name DESC, cycle DESC"),
        "duration_queue_desc": (
            "(CAST(strftime('%s', time_run) AS NUMERIC) -" +
            " CAST(strftime('%s', time_submit) AS NUMERIC)) DESC, " +
            "submit_num DESC, name DESC, cycle DESC"),
        "duration_queue_asc": (
            "(CAST(strftime('%s', time_run) AS NUMERIC) -" +
            " CAST(strftime('%s', time_submit) AS NUMERIC)) ASC, " +
            "submit_num DESC, name DESC, cycle DESC"),
        "duration_run_desc": (
            "(CAST(strftime('%s', time_run_exit) AS NUMERIC) -" +
            " CAST(strftime('%s', time_run) AS NUMERIC)) DESC, " +
            "submit_num DESC, name DESC, cycle DESC"),
        "duration_run_asc": (
            "(CAST(strftime('%s', time_run_exit) AS NUMERIC) -" +
            " CAST(strftime('%s', time_run) AS NUMERIC)) ASC, " +
            "submit_num DESC, name DESC, cycle DESC"),
        "duration_queue_run_desc": (
            "(CAST(strftime('%s', time_run_exit) AS NUMERIC) -" +
            " CAST(strftime('%s', time_submit) AS NUMERIC)) DESC, " +
            "submit_num DESC, name DESC, cycle DESC"),
        "duration_queue_run_asc": (
            "(CAST(strftime('%s', time_run_exit) AS NUMERIC) -" +
            " CAST(strftime('%s', time_submit) AS NUMERIC)) ASC, " +
            "submit_num DESC, name DESC, cycle DESC"),
    }
    JOB_STATUS_COMBOS = {
        "all": "",
        "submitted": "submit_status == 0 AND time_run IS NULL",
        "submitted,running": "submit_status == 0 AND run_status IS NULL",
        "submission-failed": "submit_status == 1",
        "submission-failed,failed": "submit_status == 1 OR run_status == 1",
        "running": "time_run IS NOT NULL AND run_status IS NULL",
        "running,succeeded,failed": "time_run IS NOT NULL",
        "succeeded": "run_status == 0",
        "succeeded,failed": "run_status IS NOT NULL",
        "failed": "run_status == 1",
    }

    REC_CYCLE_QUERY_OP = re.compile(r"\A(before |after |[<>]=?)(.+)\Z")
    REC_SEQ_LOG = re.compile(r"\A(.+\.)([^\.]+)(\.[^\.]+)\Z")
    CANNOT_JOIN_FLOW_NUMS = (
        'cannot join using column flow_nums - '
        'column not present in both tables'
    )

    def __init__(self):
        self.daos = {}

    def _db_init(self, user_name, suite_name):
        """Initialise a named CylcSuiteDAO database connection."""
        key = (user_name, suite_name)
        if key not in self.daos:
            for name in [os.path.join("log", "db"), "cylc-suite.db"]:
                db_f_name = os.path.expanduser(os.path.join(
                    get_prefix(user_name),
                    os.path.join("cylc-run",
                    suite_name, name)))
                self.daos[key] = CylcSuiteDAO(db_f_name, is_public=True)
                if os.path.exists(db_f_name):
                    break
        self.is_cylc8 = self.set_is_cylc8(user_name, suite_name)
        return self.daos[key]

    def _db_close(self, user_name, suite_name):
        """Close a named CylcSuiteDAO database connection."""
        key = (user_name, suite_name)
        if self.daos.get(key) is not None:
            self.daos[key].close()

    def _db_exec(self, user_name, suite_name, stmt, stmt_args=None):
        """Execute a query on a named CylcSuiteDAO database connection."""
        daos = self._db_init(user_name, suite_name)
        if stmt_args is None:
            stmt_args = []
        # only connect if db exists to avoid creating db if none there
        if not os.path.exists(daos.db_file_name):
            return []
        else:
            try:
                return daos.connect().execute(stmt, stmt_args)
            except sqlite3.OperationalError as exc:
                # At Cylc 8.0.1+ Workflows installed but not run will not yet
                # have a database.
                if (os.path.exists(os.path.dirname(
                    self.daos.values()[0].db_file_name) + '/flow.cylc') or
                    os.path.exists(os.path.dirname(
                        self.daos.values()[0].db_file_name) + '/suite.rc')):
                    return []
                else:
                    raise exc

    def get_suite_broadcast_states(self, user_name, suite_name):
        """Return broadcast states of a suite.
        [[point, name, key, value], ...]
        """
        stmt = CylcSuiteDAO.pre_select_broadcast_states(
            self._db_init(user_name, suite_name), order="ASC")[0]
        broadcast_states = []
        for row in self._db_exec(user_name, suite_name, stmt):
            point, namespace, key, value = row
            broadcast_states.append([point, namespace, key, value])
        return broadcast_states

    def get_suite_broadcast_events(self, user_name, suite_name):
        """Return broadcast events of a suite.
        [[time, change, point, name, key, value], ...]
        """
        stmt = CylcSuiteDAO.pre_select_broadcast_events(
            self._db_init(user_name, suite_name), order="DESC")[0]
        broadcast_events = []
        for row in self._db_exec(user_name, suite_name, stmt):
            time_, change, point, namespace, key, value = row
            broadcast_events.append(
                (time_, change, point, namespace, key, value))
        return broadcast_events

    @staticmethod
    def set_is_cylc8(user_name, suite_name):
        from cylc.review import CylcReviewService
        suite_dir = os.path.join(
            CylcReviewService._get_user_home(user_name),
            "cylc-run",
            suite_name)
        return CylcReviewService.is_cylc8(suite_dir)

    def get_suite_job_entries(
            self, user_name, suite_name, cycles, tasks, task_status,
            job_status, order, limit, offset, flow_nums='flow_nums'):
        """Query suite runtime database to return a listing of task jobs.
        user -- A string containing a valid user ID
        suite -- A string containing a valid suite ID
        cycles -- If specified, display only task jobs matching these cycles.
                  A value in the list can be a cycle, the string "before|after
                  CYCLE", or a glob to match cycles.
        tasks -- If specified, display only jobs with task names matching
                 these names. Values can be a valid task name or a glob like
                 pattern for matching valid task names.
        task_status -- If specified, it should be a list of task statuses.
                       Display only jobs in the specified list. If not
                       specified, display all jobs.
        job_status -- If specified, must be a string matching a key in
                      CylcReviewDAO.JOB_STATUS_COMBOS. Select jobs by their
                      statuses.
        order -- Order search in a predetermined way. A valid value is one of
                 the keys in CylcReviewDAO.ORDERS.
        limit -- Limit number of returned entries
        offset -- Offset entry number
        flow_nums -- whether to use flow_nums

        Return (entries, of_n_entries) where:
        entries -- A list of matching entries
        of_n_entries -- Total number of entries matching query
        Each entry is a dict:
            {"cycle": cycle, "name": name, "submit_num": submit_num,
             "events": [time_submit, time_init, time_exit],
             "task_status": task_status,
             "logs": {"script": {"path": path, "path_in_tar", path_in_tar,
                                 "size": size, "mtime": mtime},
                      "out": {...},
                      "err": {...},
                      ...}}
        eight_zero_warning - boolean flag indicating that the database is
            a Cylc 8.0 database and we can only get the latest task job.
        """
        where_expr, where_args = self._get_suite_job_entries_where(
            cycles, tasks, task_status, job_status)

        # Get number of entries
        of_n_entries = 0
        stmt = ("SELECT COUNT(*)" +
                " FROM task_states LEFT JOIN task_jobs USING (name, cycle)" +
                where_expr)
        try:
            for row in self._db_exec(user_name, suite_name, stmt, where_args):
                of_n_entries = row[0]
                break
            else:
                self._db_close(user_name, suite_name)
                return ([], 0)
        except sqlite3.Error:
            return ([], 0)
        if self.is_cylc8:
            stmt = (
                "SELECT" +
                " task_states.time_updated AS time," +
                " cycle, name," +
                " task_jobs.submit_num AS submit_num," +
                " task_states.submit_num AS submit_num_max," +
                " task_states.status AS task_status," +
                " time_submit, submit_status," +
                " time_run, time_run_exit, run_signal, run_status," +
                " platform_name, job_runner_name, job_id" +
                " FROM task_states LEFT JOIN task_jobs USING " +
                "(cycle, name, " + flow_nums + ") " +
                where_expr +
                " ORDER BY " +
                self.JOB_ORDERS.get(order, self.JOB_ORDERS["time_desc"])
            )
        else:
            stmt = (
                "SELECT" +
                " task_states.time_updated AS time," +
                " cycle, name," +
                " task_jobs.submit_num AS submit_num," +
                " task_states.submit_num AS submit_num_max," +
                " task_states.status AS task_status," +
                " time_submit, submit_status," +
                " time_run, time_run_exit, run_signal, run_status," +
                " user_at_host, batch_sys_name, batch_sys_job_id" +
                " FROM task_states LEFT JOIN task_jobs USING (cycle, name)" +
                where_expr +
                " ORDER BY " +
                self.JOB_ORDERS.get(order, self.JOB_ORDERS["time_desc"])
            )
        # Get entries
        entries = []
        entry_of = {}

        limit_args = []
        if limit:
            stmt += " LIMIT ? OFFSET ?"
            limit_args = [limit, offset]

        # Try except loop deals with case (Cylc 8.0) where the database
        # doesn't contain enough information to identify multiple jobs
        # belonging to the same task:
        # https://github.com/cylc/cylc-flow/issues/5247
        eight_zero_warning = False
        try:
            db_data = self._db_exec(
                user_name, suite_name, stmt, where_args + limit_args
            )
        except OperationalError as exc:
            if exc.message == self.CANNOT_JOIN_FLOW_NUMS:
                stmt = stmt.replace('flow_nums', 'submit_num')
                db_data = self._db_exec(
                   user_name, suite_name, stmt, where_args + limit_args
                )
                eight_zero_warning = True
            else:
                raise exc

        for row in db_data:
            (
                cycle, name, submit_num, submit_num_max, task_status,
                time_submit, submit_status,
                time_run, time_run_exit, run_signal, run_status,
                user_at_host, batch_sys_name, batch_sys_job_id
            ) = row[1:]
            entry = {
                "cycle": cycle,
                "name": name,
                "submit_num": submit_num or 0,
                "submit_num_max": submit_num_max,
                "events": [time_submit, time_run, time_run_exit],
                "task_status": task_status,
                "submit_status": submit_status,
                "run_signal": run_signal,
                "run_status": run_status,
                "host": user_at_host,
                "submit_method": batch_sys_name,
                "submit_method_id": batch_sys_job_id,
                "logs": {},
                "seq_logs_indexes": {}}
            entries.append(entry)
            entry_of[(cycle, name, submit_num)] = entry
        self._db_close(user_name, suite_name)
        if entries:
            self._get_job_logs(user_name, suite_name, entries, entry_of)
        return (entries, of_n_entries, eight_zero_warning)

    def _get_suite_job_entries_where(
            self, cycles, tasks, task_status, job_status):
        """Helper for get_suite_job_entries.
        Get query's "WHERE" expression and its arguments.
        """
        where_exprs = []
        where_args = []
        if cycles:
            cycle_where_exprs = []
            for cycle in cycles:
                match = self.REC_CYCLE_QUERY_OP.match(cycle)
                if match:
                    operator, operand = match.groups()
                    where_args.append(operand)
                    if operator == "before ":
                        cycle_where_exprs.append("cycle <= ?")
                    elif operator == "after ":
                        cycle_where_exprs.append("cycle >= ?")
                    else:
                        cycle_where_exprs.append("cycle %s ?" % operator)
                else:
                    where_args.append(cycle)
                    cycle_where_exprs.append("cycle GLOB ?")
            where_exprs.append(" OR ".join(cycle_where_exprs))
        if tasks:
            where_exprs.append(" OR ".join(["name GLOB ?"] * len(tasks)))
            where_args += tasks
        if task_status:
            task_status_where_exprs = []
            for item in task_status:
                task_status_where_exprs.append("task_states.status == ?")
                where_args.append(item)
            where_exprs.append(" OR ".join(task_status_where_exprs))
        try:
            job_status_where = self.JOB_STATUS_COMBOS[job_status]
        except KeyError:
            pass
        else:
            if job_status_where:
                where_exprs.append(job_status_where)
        if where_exprs:
            return (" WHERE (" + ") AND (".join(where_exprs) + ")", where_args)
        else:
            return ("", where_args)

    def _get_job_logs(self, user_name, suite_name, entries, entry_of):
        """Helper for "get_suite_job_entries". Get job logs.
        Recent job logs are likely to be in the file system, so we can get a
        listing of the relevant "log/job/CYCLE/NAME/SUBMI_NUM/" directory.
        Older job logs may be archived in "log/job-CYCLE.tar.gz", we should
        only open each relevant TAR file once to obtain a listing for all
        relevant entries of that cycle.
        Modify each entry in entries.
        """
        user_suite_dir = os.path.expanduser(os.path.join(
            get_prefix(user_name), os.path.join("cylc-run", suite_name)))
        try:
            fs_log_cycles = os.listdir(
                os.path.join(user_suite_dir, "log", "job"))
        except OSError:
            fs_log_cycles = []
        targzip_log_cycles = []
        for name in glob(os.path.join(user_suite_dir, "log", "job-*.tar.gz")):
            targzip_log_cycles.append(os.path.basename(name)[4:-7])

        relevant_targzip_log_cycles = []
        for entry in entries:
            if entry["cycle"] in fs_log_cycles:
                pathd = "log/job/%(cycle)s/%(name)s/%(submit_num)02d" % entry
                try:
                    filenames = os.listdir(os.path.join(user_suite_dir, pathd))
                except OSError:
                    continue
                for filename in filenames:
                    try:
                        stat = os.stat(
                            os.path.join(user_suite_dir, pathd, filename))
                    except OSError:
                        pass
                    else:
                        entry["logs"][filename] = {
                            "path": "/".join([pathd, filename]),
                            "path_in_tar": None,
                            "mtime": int(stat.st_mtime),  # int precise enough
                            "size": stat.st_size,
                            "exists": True,
                            "seq_key": None}
                        continue
            if entry["cycle"] in targzip_log_cycles:
                if entry["cycle"] not in relevant_targzip_log_cycles:
                    relevant_targzip_log_cycles.append(entry["cycle"])

        for cycle in relevant_targzip_log_cycles:
            path = os.path.join("log", "job-%s.tar.gz" % cycle)
            tar = tarfile.open(os.path.join(user_suite_dir, path), "r:gz")
            for member in tar.getmembers():
                # member.name expected to be "job/cycle/task/submit_num/*"
                if not member.isfile():
                    continue
                try:
                    cycle_str, name, submit_num_str = (
                        member.name.split("/", 4)[1:4])
                    entry = entry_of[(cycle_str, name, int(submit_num_str))]
                except (KeyError, ValueError):
                    continue
                entry["logs"][os.path.basename(member.name)] = {
                    "path": path,
                    "path_in_tar": member.name,
                    "mtime": int(member.mtime),  # too precise otherwise
                    "size": member.size,
                    "exists": True,
                    "seq_key": None}

        # Sequential logs
        for entry in entries:
            for filename, filename_items in entry["logs"].items():
                seq_log_match = self.REC_SEQ_LOG.match(filename)
                if not seq_log_match:
                    continue
                head, index_str, tail = seq_log_match.groups()
                seq_key = head + "*" + tail
                filename_items["seq_key"] = seq_key
                if seq_key not in entry["seq_logs_indexes"]:
                    entry["seq_logs_indexes"][seq_key] = {}
                entry["seq_logs_indexes"][seq_key][index_str] = filename
            for seq_key, indexes in entry["seq_logs_indexes"].items():
                # Only one item, not a sequence
                if len(indexes) <= 1:
                    entry["seq_logs_indexes"].pop(seq_key)
                # All index_str are numbers, convert key to integer so
                # the template can sort them as numbers
                try:
                    int_indexes = {}
                    for index_str, filename in indexes.items():
                        int_indexes[int(index_str)] = filename
                    entry["seq_logs_indexes"][seq_key] = int_indexes
                except ValueError:
                    pass
            for filename, log_dict in entry["logs"].items():
                # Unset seq_key for singular items
                if log_dict["seq_key"] not in entry["seq_logs_indexes"]:
                    log_dict["seq_key"] = None

    def get_suite_cycles_summary(
            self, user_name, suite_name, order, limit, offset):
        """Return a the state summary (of each cycle) of a user's suite.
        user -- A string containing a valid user ID
        suite -- A string containing a valid suite ID
        limit -- Limit number of returned entries
        offset -- Offset entry number
        Return (entries, of_n_entries), where entries is a data structure that
        looks like:
            [   {   "cycle": cycle,
                    "n_states": {
                        "active": N, "success": M, "fail": L, "job_fails": K,
                    },
                    "max_time_updated": T2,
                },
                # ...
            ]
        where:
        * cycle is a date-time cycle label
        * N, M, L, K are the numbers of tasks in given states
        * T2 is the time when last update time of (a task in) the cycle
        and of_n_entries is the total number of entries.
        """

        of_n_entries = 0
        stmt = ("SELECT COUNT(DISTINCT cycle) FROM task_states WHERE " +
                "submit_num > 0")
        try:
            for row in self._db_exec(user_name, suite_name, stmt):
                of_n_entries = row[0]
                break
        except sqlite3.Error:
            return ([], 0)
        if not of_n_entries:
            self._db_close(user_name, suite_name)
            return ([], 0)

        # Not strictly correct, if cycle is in basic date-only format,
        # but should not matter for most cases
        integer_mode = False
        stmt = "SELECT cycle FROM task_states LIMIT 1"
        for row in self._db_exec(user_name, suite_name, stmt):
            integer_mode = row[0].isdigit()
            break

        user_suite_dir = os.path.expanduser(os.path.join(
            get_prefix(user_name), os.path.join("cylc-run", suite_name)))
        targzip_log_cycles = []
        try:
            for item in os.listdir(os.path.join(user_suite_dir, "log")):
                if item.startswith("job-") and item.endswith(".tar.gz"):
                    targzip_log_cycles.append(item[4:-7])
        except OSError:
            pass

        if self.is_cylc8:
            # Cylc 8 has a smaller set of task states.
            # There is no way of identifying
            # queued, runahead, retrying and submit-retrying from
            # other waiting tasks.
            task_status_groups = {
                'active': ['running', 'preparing', 'submitted'],
                'fail': ['failed', 'submit-failed'],
                'success': ['expired', 'succeeded']
            }
        else:
            task_status_groups = TASK_STATUS_GROUPS

        states_stmt = {}
        for key, names in task_status_groups.items():
            states_stmt[key] = " OR ".join(
                ["status=='%s'" % (name) for name in names])

        stmt = (
            "SELECT" +
            " cycle," +
            " max(time_updated)," +
            " sum(" + states_stmt["active"] + ") AS n_active," +
            " sum(" + states_stmt["success"] + ") AS n_success,"
            " sum(" + states_stmt["fail"] + ") AS n_fail"
            " FROM task_states" +
            " GROUP BY cycle" +
            " HAVING n_active > 0" +
            " OR n_success > 0" +
            " OR n_fail >0"
        )
        if integer_mode:
            stmt += " ORDER BY cast(cycle as number)"
        else:
            stmt += " ORDER BY cycle"
        stmt += self.CYCLE_ORDERS.get(order, self.CYCLE_ORDERS["time_desc"])
        stmt_args = []
        if limit:
            stmt += " LIMIT ? OFFSET ?"
            stmt_args += [limit, offset]
        entry_of = {}
        entries = []
        for row in self._db_exec(user_name, suite_name, stmt, stmt_args):
            cycle, max_time_updated, n_active, n_success, n_fail = row
            entry_of[cycle] = {
                "cycle": cycle,
                "has_log_job_tar_gz": cycle in targzip_log_cycles,
                "max_time_updated": max_time_updated,
                "n_states": {
                    "active": n_active,
                    "success": n_success,
                    "fail": n_fail,
                    "job_active": 0,
                    "job_success": 0,
                    "job_fail": 0,
                },
            }
            entries.append(entry_of[cycle])
        self._db_close(user_name, suite_name)

        # Check if "task_jobs" table is available or not.
        # Note: A single query with a JOIN is probably a more elegant solution.
        # However, timing tests suggest that it is cheaper with 2 queries.
        # This 2nd query may return more results than is necessary, but should
        # be a very cheap query as it does not have to do a lot of work.
        check_stmt = "SELECT name FROM sqlite_master WHERE name==?"
        check_query = self._db_exec(user_name, suite_name, check_stmt,
                                    ["task_jobs"])
        if check_query.fetchone() is not None:
            stmt = (
                "SELECT cycle," +
                " sum(" + self.JOB_STATUS_COMBOS["submitted,running"] +
                ") AS n_job_active," +
                " sum(" + self.JOB_STATUS_COMBOS["succeeded"] +
                ") AS n_job_success," +
                " sum(" + self.JOB_STATUS_COMBOS["submission-failed,failed"] +
                ") AS n_job_fail" +
                " FROM task_jobs GROUP BY cycle")
        else:
            fail_events_stmt = " OR ".join(
                ["event=='%s'" % (name)
                 for name in TASK_STATUS_GROUPS["fail"]])
            stmt = (
                "SELECT cycle," +
                " sum(" + fail_events_stmt + ") AS n_job_fail" +
                " FROM task_events GROUP BY cycle")
        self._db_close(user_name, suite_name)
        for cycle, n_job_active, n_job_success, n_job_fail in self._db_exec(
                user_name, suite_name, stmt):
            try:
                entry_of[cycle]["n_states"]["job_active"] = n_job_active
                entry_of[cycle]["n_states"]["job_success"] = n_job_success
                entry_of[cycle]["n_states"]["job_fail"] = n_job_fail
            except KeyError:
                pass
            else:
                del entry_of[cycle]
                if not entry_of:
                    break
        self._db_close(user_name, suite_name)

        return entries, of_n_entries

    def get_suite_state_summary(self, user_name, suite_name):
        """Return a the state summary of a user's suite.
        Return {"is_running": b, "is_failed": b, "server": s}
        where:
        * is_running is a boolean to indicate if the suite is running
        * is_failed: a boolean to indicate if any tasks (submit) failed
        * server: host:port of server, if available
        """
        ret = {
            "is_running": False,
            "is_failed": False,
            "server": None}
        dao = self._db_init(user_name, suite_name)
        if not os.access(dao.db_file_name, os.F_OK | os.R_OK):
            self._db_close(user_name, suite_name)
            return ret

        port_file_path = os.path.expanduser(
            os.path.join(
                "~" + user_name, "cylc-run", suite_name, ".service",
                "contact"))
        try:
            host = None
            port_str = None
            for line in open(port_file_path):
                key, value = [item.strip() for item in line.split("=", 1)]
                if key in ["CYLC_SUITE_HOST", "CYLC_WORKFLOW_HOST"]:
                    host = value
                elif key in ["CYLC_SUITE_PORT", "CYLC_WORKFLOW_PORT"]:
                    port_str = value
        except (IOError, ValueError):
            pass
        else:
            if host and port_str:
                ret["is_running"] = True
                ret["server"] = host.split(".", 1)[0] + ":" + port_str

        stmt = "SELECT status FROM task_states WHERE status GLOB ? LIMIT 1"
        stmt_args = ["*failed"]
        try:
            for _ in self._db_exec(user_name, suite_name, stmt, stmt_args):
                ret["is_failed"] = True
                break
        except sqlite3.Error:
            pass  # case with no task_states table.
        self._db_close(user_name, suite_name)

        return ret
