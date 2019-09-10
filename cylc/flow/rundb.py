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
"""Provide data access object for the suite runtime database."""

import os
import re
import traceback
from collections import defaultdict
from contextlib import suppress
from typing import Dict, List, Union

from sqlalchemy import (
    cast, Column, create_engine, func, INTEGER, NUMERIC, REAL, Table, TEXT,
    MetaData)
from sqlalchemy.engine.base import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import and_, or_, select
from sqlalchemy.sql.dml import ValuesBase
from sqlalchemy.sql.expression import Select

import cylc.flow.flags
from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.platform_lookup import reverse_lookup
from cylc.flow.wallclock import get_current_time_string

meta = MetaData()


# --- tables

broadcast_events = Table(
    'broadcast_events', meta,
    Column('time', TEXT),
    Column('change', TEXT),
    Column('point', TEXT),
    Column('namespace', TEXT),
    Column('key', TEXT),
    Column('value', TEXT)
)

broadcast_states = Table(
    'broadcast_states', meta,
    Column('point', TEXT, primary_key=True),
    Column('namespace', TEXT, primary_key=True),
    Column('key', TEXT, primary_key=True),
    Column('value', TEXT)
)

broadcast_states_checkpoints = Table(
    'broadcast_states_checkpoints', meta,
    Column('id', INTEGER, primary_key=True),
    Column('point', TEXT, primary_key=True),
    Column('namespace', TEXT, primary_key=True),
    Column('key', TEXT, primary_key=True),
    Column('value', TEXT)
)

checkpoint_id = Table(
    'checkpoint_id', meta,
    Column('id', INTEGER, primary_key=True),
    Column('time', TEXT),
    Column('event', TEXT)
)

inheritance = Table(
    'inheritance', meta,
    Column('namespace', TEXT, primary_key=True),
    Column('inheritance', TEXT)
)

suite_params = Table(
    'suite_params', meta,
    Column('key', TEXT, primary_key=True),
    Column('value', TEXT)
)

suite_params_checkpoints = Table(
    'suite_params_checkpoints', meta,
    Column('id', INTEGER, primary_key=True),
    Column('key', TEXT, primary_key=True),
    Column('value', TEXT)
)

suite_template_vars = Table(
    'suite_template_vars', meta,
    Column('key', TEXT, primary_key=True),
    Column('value', TEXT)
)

task_action_timers = Table(
    'task_action_timers', meta,
    Column('cycle', TEXT, primary_key=True),
    Column('name', TEXT, primary_key=True),
    Column('ctx_key', TEXT, primary_key=True),
    Column('ctx', TEXT),
    Column('delays', TEXT),
    Column('num', INTEGER),
    Column('delay', TEXT),
    Column('timeout', TEXT)
)

task_jobs = Table(
    'task_jobs', meta,
    Column('cycle', TEXT, primary_key=True),
    Column('name', TEXT, primary_key=True),
    Column('submit_num', INTEGER, primary_key=True),
    Column('is_manual_submit', INTEGER),
    Column('try_num', INTEGER),
    Column('time_submit', TEXT),
    Column('time_submit_exit', TEXT),
    Column('submit_status', INTEGER),
    Column('time_run', TEXT),
    Column('time_run_exit', TEXT),
    Column('run_signal', TEXT),
    Column('run_status', INTEGER),
    Column('user_at_host', TEXT),
    Column('batch_sys_name', TEXT),
    Column('batch_sys_job_id', TEXT)
)

task_events = Table(
    'task_events', meta,
    Column('name', TEXT),
    Column('cycle', TEXT),
    Column('time', TEXT),
    Column('submit_num', INTEGER),
    Column('event', TEXT),
    Column('message', TEXT)
)

task_late_flags = Table(
    'task_late_flags', meta,
    Column('cycle', TEXT, primary_key=True),
    Column('name', TEXT, primary_key=True),
    Column('value', INTEGER)
)

task_outputs = Table(
    'task_outputs', meta,
    Column('cycle', TEXT, primary_key=True),
    Column('name', TEXT, primary_key=True),
    Column('outputs', TEXT)
)

task_pool = Table(
    'task_pool', meta,
    Column('cycle', TEXT, primary_key=True),
    Column('name', TEXT, primary_key=True),
    Column('spawned', INTEGER),
    Column('status', TEXT),
    Column('is_held', INTEGER)
)

xtriggers = Table(
    'xtriggers', meta,
    Column('signature', TEXT, primary_key=True),
    Column('results', TEXT)
)

task_pool_checkpoints = Table(
    'task_pool_checkpoints', meta,
    Column('id', INTEGER, primary_key=True),
    Column('cycle', TEXT, primary_key=True),
    Column('name', TEXT, primary_key=True),
    Column('spawned', INTEGER),
    Column('status', TEXT),
    Column('is_held', INTEGER)
)

task_states = Table(
    'task_states', meta,
    Column('name', TEXT, primary_key=True),
    Column('cycle', TEXT, primary_key=True),
    Column('time_created', TEXT),
    Column('time_updated', TEXT),
    Column('submit_num', INTEGER),
    Column('status', TEXT)
)

task_timeout_timers = Table(
    'task_timeout_timers', meta,
    Column('cycle', TEXT, primary_key=True),
    Column('name', TEXT, primary_key=True),
    Column('timeout', REAL)
)

# ---


class CylcSuiteDAO(object):
    """Data access object for the suite runtime database."""

    DB_FILE_BASE_NAME = "db"
    MAX_TRIES = 100
    CHECKPOINT_LATEST_ID = 0
    CHECKPOINT_LATEST_EVENT = "latest"

    def __init__(self, file_name: str, is_public=False, timeout=0.2):
        """Initialise object.

        FIXME: we must receive a connection URL, not a SQLite DB name
        conn_url (str) - DB connection URL, e.g. sqlite:///tmp/file.db
        is_public (bool) - If True, allow retries, etc
        """
        self.conn_url = "sqlite://" if file_name == '' \
            else f"sqlite:///{file_name}"
        self.engine = create_engine(
            self.conn_url,
            connect_args={
                'timeout': timeout
            },
            echo=False
        )
        if self.is_sqlite() and file_name != '':
            # create if file does not exist
            self.db_file_name = self._get_db_file_name()
            os.makedirs(os.path.dirname(self.db_file_name), exist_ok=True)
        else:
            self.db_file_name = None

        self.is_public = is_public
        self.conn = None  # type: Union[Connection, None]
        self.n_tries = 0

        if not self.is_public:
            self.create_tables()

        self.to_delete = defaultdict(list)  # type: Dict[Table, List]
        self.to_insert = defaultdict(list)  # type: Dict[Table, List]
        self.to_update = defaultdict(list)  # type: Dict[Table, List]

    def _get_db_file_name(self) -> str:
        return re.sub("sqlite.*:///", "", self.conn_url)

    def add_delete_item(self, table: Table, where_args: dict = None):
        """Queue a DELETE item for a given table.

        where_args should be a dict, update will only apply to rows matching
        all these items.

        """
        s = table.delete()
        if where_args:
            for left, right in where_args.items():
                if left in table.c:
                    s = s.where(table.c[left] == right)
        self.to_delete[table.name].append(s)

    def add_insert_item(self, table: Table, args: dict):
        """Queue an INSERT args for a given table.

        If args is a list, its length will be adjusted to be the same as the
        number of columns. If args is a dict, will return a list with the same
        length as the number of columns, the elements of which are determined
        by matching the column names with the keys in the dict.

        Empty elements are padded with None.

        """
        self.to_insert[table.name].append([table.insert(), args])

    def add_update_item(self, table: Table, set_args: dict,
                        where_args=None):
        """Queue an UPDATE item for a given table.

        set_args should be a dict, with column keys and values to be set.
        where_args should be a dict, update will only apply to rows matching
        all these items.

        """
        s = table.update()
        if where_args:
            for left, right in where_args.items():
                if left in table.c:
                    s = s.where(table.c[left] == right)
        self.to_update[table.name].append([s, set_args])

    # TODO: make it a context manager
    def close(self):
        """Explicitly close the connection."""
        if self.conn is not None:
            with suppress(Exception):
                self.conn.close()
            self.conn = None

    def connect(self) -> Connection:
        """Connect to the database.

        Returns:
            Connection: a SQLAlchemy connection object
        """
        if self.conn is None or self.conn.closed:
            self.conn = self.engine.connect()
        return self.conn

    def create_tables(self):
        """Create tables."""
        meta.create_all(self.engine)

    def execute_queued_items(self):
        """Execute queued items for each table."""
        if not self.to_insert and not self.to_delete and not self.to_update:
            return
        with self.connect() as conn:
            with conn.begin() as trans:
                try:
                    for table_name in meta.tables:
                        if table_name in self.to_delete:
                            for stmt in self.to_delete[table_name]:
                                self._execute_stmt(stmt, [], conn)
                        if table_name in self.to_insert:
                            # TODO: old code computed executemany for inserts
                            for stmt, args in self.to_insert.get(table_name):
                                # TODO: sqlite-specific "insert or replace"!
                                if self.is_sqlite():
                                    stmt = stmt.prefix_with("OR REPLACE",
                                                            dialect="sqlite")
                                self._execute_stmt(stmt, args, conn)
                        if table_name in self.to_update:
                            for stmt, args in self.to_update[table_name]:
                                self._execute_stmt(stmt, args, conn)
                    trans.commit()
                except SQLAlchemyError:
                    if not self.is_public:
                        raise
                    self.n_tries += 1
                    if self.is_sqlite():
                        LOG.warning(
                            "%(file)s: write attempt (%(attempt)d) did not "
                            "complete\n" % {"file": self.db_file_name,
                                            "attempt": self.n_tries})
                    else:
                        LOG.warning(
                            "write attempt (%(attempt)d) did not "
                            "complete\n" % {"attempt": self.n_tries})
                    with suppress(SQLAlchemyError):
                        trans.rollback()
                else:
                    # Clear the queues
                    self.to_delete.clear()
                    self.to_insert.clear()
                    self.to_update.clear()
                    # Report public database retry recovery if necessary
                    if self.n_tries:
                        if self.is_sqlite():
                            LOG.warning(
                                "%(file)s: recovered after (%(attempt)d)"
                                "attempt(s)\n" % {"file": self.db_file_name,
                                                  "attempt": self.n_tries})
                        else:
                            LOG.warning(
                                "recovered after (%(attempt)d)"
                                "attempt(s)\n" % {"attempt": self.n_tries})
                    self.n_tries = 0

    def _execute_stmt(self, stmt: ValuesBase, stmt_args_list: List[Dict],
                      conn: Connection):
        """Helper for "self.execute_queued_items".

        Execute a statement. If this is the public database, return True on
        success and False on failure. If this is the private database, return
        True on success, and raise on failure.
        """
        try:
            conn.execute(stmt, stmt_args_list)
        except SQLAlchemyError:
            if not self.is_public:
                raise
            if cylc.flow.flags.debug:
                traceback.print_exc()
            if self.is_sqlite():
                err_log = (
                    "cannot execute database statement:\n"
                    "file=%(file)s:\nstmt=%(stmt)s"
                ) % {"file": self.db_file_name, "stmt": stmt}
            else:
                err_log = "cannot execute database statement:\n" \
                          "stmt=%(stmt)s" % {"stmt": stmt}
            for i, stmt_args in enumerate(stmt_args_list):
                err_log += ("\nstmt_args[%(i)d]=%(stmt_args)s" % {
                    "i": i, "stmt_args": stmt_args})
            LOG.warning(err_log)
            raise

    def pre_select_broadcast_states(self, id_key=None, order=None):
        """Query statement and args formation for select_broadcast_states."""
        is_checkpoint = id_key is not None \
            and id_key != self.CHECKPOINT_LATEST_ID
        table = broadcast_states_checkpoints if is_checkpoint \
            else broadcast_states
        s = select([
            table.c.point,
            table.c.namespace,
            table.c.key,
            table.c.value
        ])
        if order == "ASC":
            s = s.order_by(
                table.c.point.asc(),
                table.c.namespace.asc(),
                table.c.key.asc()
            )
        if is_checkpoint:
            s = s.where(table.c.id == id_key)
        with self.connect() as conn:
            return conn.execute(s).fetchall()

    def select_broadcast_states(self, callback, id_key=None, sort=None):
        """Select from broadcast_states or broadcast_states_checkpoints.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [point, namespace, key, value]

        If id_key is specified,
        select from broadcast_states table if id_key == CHECKPOINT_LATEST_ID.
        Otherwise select from broadcast_states_checkpoints where id == id_key.
        """
        broadcast_states_result = self.pre_select_broadcast_states(
            id_key=None, order=sort)
        for row_idx, row in enumerate(broadcast_states_result):
            callback(row_idx, list(row))

    def pre_select_broadcast_events(self, order=None):
        """Query statement and args formation for select_broadcast_events."""
        s = select([
            broadcast_events.c.time,
            broadcast_events.c.change,
            broadcast_events.c.point,
            broadcast_events.c.namespace,
            broadcast_events.c.key,
            broadcast_events.c.value
        ])
        if order == "DESC":
            s = s.order_by(
                broadcast_events.c.time.desc(),
                broadcast_events.c.point.desc(),
                broadcast_events.c.namespace.desc(),
                broadcast_events.c.key.desc()
            )
        with self.connect() as conn:
            return conn.execute(s).fetchall()

    def select_broadcast_events(self, callback, id_key=None, sort=None):
        """Select from broadcast_events.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [time, change, point, namespace, key, value]
        """
        broadcast_events_results = self.pre_select_broadcast_events(
            order=sort)
        for row_idx, row in enumerate(broadcast_events_results):
            callback(row_idx, list(row))

    def select_checkpoint_id(self, callback, id_key=None):
        """Select from checkpoint_id.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [id, time, event]

        If id_key is specified, add where id == id_key to select.
        """
        s = select([
            checkpoint_id.c.id,
            checkpoint_id.c.time,
            checkpoint_id.c.event
        ])
        if id_key is not None:
            s = s.where(checkpoint_id.c.id == id_key)
        s = s.order_by(checkpoint_id.c.time.asc())
        with self.connect() as conn:
            for row_idx, row in enumerate(conn.execute(s).fetchall()):
                callback(row_idx, list(row))

    def select_checkpoint_id_restart_count(self):
        """Return number of restart event in checkpoint_id table."""
        s = select([
            func.count(checkpoint_id.c.event)
        ]).select_from(
            checkpoint_id
        ).where(checkpoint_id.c.event == 'restart')
        with self.connect() as conn:
            for row in conn.execute(s).fetchall():
                return row[0]
        return 0

    def select_suite_params(self, callback, id_key=None):
        """Select from suite_params or suite_params_checkpoints.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [key,value]

        If id_key is specified,
        select from suite_params table if id_key == CHECKPOINT_LATEST_ID.
        Otherwise select from suite_params_checkpoints where id == id_key.
        """
        if id_key is None or id_key == self.CHECKPOINT_LATEST_ID:
            s = select([
                suite_params.c.key,
                suite_params.c.value
            ])
        else:
            s = select([
                suite_params_checkpoints.c.key,
                suite_params_checkpoints.c.value
            ]).where(suite_params_checkpoints.c.id == id_key)
        with self.connect() as conn:
            for row_idx, row in enumerate(conn.execute(s).fetchall()):
                callback(row_idx, list(row))

    def select_suite_template_vars(self, callback):
        """Select from suite_template_vars.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [key,value]
        """
        s = select([
            suite_template_vars.c.key,
            suite_template_vars.c.value
        ])
        with self.connect() as conn:
            for row_idx, row in enumerate(conn.execute(s).fetchall()):
                callback(row_idx, list(row))

    def select_task_action_timers(self, callback):
        """Select from task_action_timers for restart.

        Invoke callback(row_idx, row) on each row.
        """
        s = select([column for column in task_action_timers.c])
        with self.connect() as conn:
            for row_idx, row in enumerate(conn.execute(s).fetchall()):
                callback(row_idx, list(row))

    def select_task_job(self, cycle: str, name: str, submit_num: str = None):
        """Select items from task_jobs by (cycle, name, submit_num).

        :return: a dict for mapping keys to the column values
        :rtype: dict
        """
        columns = [
            task_jobs.c.is_manual_submit,
            task_jobs.c.try_num,
            task_jobs.c.time_submit,
            task_jobs.c.time_submit_exit,
            task_jobs.c.submit_status,
            task_jobs.c.time_run,
            task_jobs.c.time_run_exit,
            task_jobs.c.run_signal,
            task_jobs.c.run_status,
            task_jobs.c.user_at_host,
            task_jobs.c.batch_sys_name,
            task_jobs.c.batch_sys_job_id
        ]
        s = select(columns=columns)
        if submit_num in [None, "NN"]:
            s = s.where(
                and_(
                    task_jobs.c.cycle == cycle,
                    task_jobs.c.name == name
                )
            ).order_by(
                task_jobs.c.submit_num
            )
        else:
            s = s.where(
                and_(
                    task_jobs.c.cycle == cycle,
                    task_jobs.c.name == name,
                    task_jobs.c.submit_num == submit_num
                )
            )
        with suppress(Exception):
            with self.connect() as conn:
                for row in conn.execute(s).fetchall():
                    ret = {}
                    for key, value in zip([c.name for c in columns], row):
                        ret[key] = value
                    return ret

    def select_task_job_run_times(self, callback):
        """Select run times of succeeded task jobs grouped by task names.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [name, run_times_str]

        where run_times_str is a string containing comma separated list of
        integer run times. This method is used to re-populate elapsed run times
        of each task on restart.
        """
        s = select([
            task_jobs.c.name,
            func.group_concat(
                cast(task_jobs.c.time_run_exit, NUMERIC) -
                cast(task_jobs.c.time_run, NUMERIC)
            )
        ]).select_from(task_jobs)\
            .where(task_jobs.c.run_status == 0)\
            .group_by(task_jobs.c.name)\
            .order_by(task_jobs.c.time_run_exit)
        with self.connect() as conn:
            for row_idx, row in enumerate(conn.execute(s).fetchall()):
                callback(row_idx, list(row))

    def select_submit_nums_for_insert(self, task_ids):
        """Select name,cycle,submit_num from task_states.

        Fetch submit numbers for tasks on insert.
        Return a data structure like this:

        {
            (name1, point1): submit_num,
            ...,
        }

        task_ids should be specified as [(name-glob, cycle), ...]

        Args:
            task_ids (list): A list of tuples, with the name-glob and cycle
                of a task.
        """
        ret = {}
        with self.connect() as conn:
            for task_name, task_cycle in task_ids:
                s = select([
                    task_states.c.name,
                    task_states.c.cycle,
                    task_states.c.submit_num
                ]).where(
                    and_(
                        task_states.c.name == task_name,
                        task_states.c.cycle == task_cycle
                    )
                )
                for name, cycle, submit_num in conn.execute(s).fetchall():
                    ret[(name, cycle)] = submit_num
        return ret

    def select_xtriggers_for_restart(self, callback):
        s = select([
            xtriggers.c.signature,
            xtriggers.c.results
        ])
        with self.connect() as conn:
            for row_idx, row in enumerate(conn.execute(s).fetchall()):
                callback(row_idx, list(row))

    def select_task_pool(self, callback, id_key=None):
        """Select from task_pool or task_pool_checkpoints.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [cycle, name, spawned, status]

        If id_key is specified,
        select from task_pool table if id_key == CHECKPOINT_LATEST_ID.
        Otherwise select from task_pool_checkpoints where id == id_key.
        """
        if id_key is None or id_key == self.CHECKPOINT_LATEST_ID:
            s = select([
                task_pool.c.cycle,
                task_pool.c.name,
                task_pool.c.spawned,
                task_pool.c.status,
                task_pool.c.is_held
            ])
        else:
            s = select([
                task_pool_checkpoints.c.cycle,
                task_pool_checkpoints.c.name,
                task_pool_checkpoints.c.spawned,
                task_pool_checkpoints.c.status,
                task_pool_checkpoints.c.is_held
            ]).where(task_pool_checkpoints.c.id == id_key)
        with self.connect() as conn:
            for row_idx, row in enumerate(conn.execute(s).fetchall()):
                callback(row_idx, list(row))

    def select_task_pool_for_restart(self, callback, id_key=None):
        """Select from task_pool+task_states+task_jobs for restart.

        Invoke callback(row_idx, row) on each row, where each row contains:
            [cycle, name, spawned, is_late, status, is_held, submit_num,
             try_num, user_at_host, time_submit, time_run, timeout, outputs]

        If id_key is specified,
        select from task_pool table if id_key == CHECKPOINT_LATEST_ID.
        Otherwise select from task_pool_checkpoints where id == id_key.
        """
        is_checkpoint = id_key is not None \
            and id_key != self.CHECKPOINT_LATEST_ID
        table = task_pool_checkpoints if is_checkpoint else task_pool
        s = Select(
            from_obj=table,
            columns=[
                table.c.cycle,
                table.c.name,
                table.c.spawned,
                task_late_flags.c.value,
                table.c.status,
                table.c.is_held,
                task_states.c.submit_num,
                task_jobs.c.try_num,
                task_jobs.c.user_at_host,
                task_jobs.c.time_submit,
                task_jobs.c.time_run,
                task_timeout_timers.c.timeout,
                task_outputs.c.outputs
            ])

        if is_checkpoint:
            s = s.where(table.c.id == id_key)

        s.append_from(
            table.join(
                task_states,
                onclause=and_(
                    table.c.cycle == task_states.c.cycle,
                    table.c.name == task_states.c.name
                )
            ).join(
                task_late_flags,
                onclause=and_(
                    table.c.cycle == task_late_flags.c.cycle,
                    table.c.name == task_late_flags.c.name
                ),
                isouter=True
            ).join(
                task_jobs,
                onclause=and_(
                    table.c.cycle == task_jobs.c.cycle,
                    table.c.name == task_jobs.c.name,
                    task_states.c.submit_num == task_jobs.c.submit_num
                ),
                isouter=True
            ).join(
                task_timeout_timers,
                onclause=and_(
                    table.c.cycle == task_timeout_timers.c.cycle,
                    table.c.name == task_timeout_timers.c.name
                ),
                isouter=True
            ).join(
                task_outputs,
                onclause=and_(
                    table.c.cycle == task_outputs.c.cycle,
                    table.c.name == task_outputs.c.name
                ),
                isouter=True
            )
        )
        with self.connect() as conn:
            for row_idx, row in enumerate(conn.execute(s).fetchall()):
                callback(row_idx, list(row))

    def select_task_times(self):
        """Select submit/start/stop times to compute job timings.

        To make data interpretation easier, choose the most recent succeeded
        task to sample timings from.
        """
        s = select([
            task_jobs.c.name,
            task_jobs.c.cycle,
            task_jobs.c.user_at_host,
            task_jobs.c.batch_sys_name,
            task_jobs.c.time_submit,
            task_jobs.c.time_run,
            task_jobs.c.time_run_exit
        ]).where(task_jobs.c.run_status == 0)
        columns = (
            'name', 'cycle', 'host', 'batch_system',
            'submit_time', 'start_time', 'succeed_time'
        )
        with self.connect() as conn:
            return columns, [r for r in conn.execute(s).fetchall()]

    def take_checkpoints(self, event, other_daos: List['CylcSuiteDAO'] = None):
        """Add insert items to *_checkpoints tables.

        Select items in suite_params, broadcast_states and task_pool and
        prepare them for insert into the relevant *_checkpoints tables, and
        prepare an insert into the checkpoint_id table the event and the
        current time.

        If other_daos is a specified, it should be a list of CylcSuiteDAO
        objects.  The logic will prepare insertion of the same items into the
        *_checkpoints tables of these DAOs as well.
        """
        if other_daos is None:
            other_daos = []
        daos = [self, *other_daos]

        s = select(
            [func.max(checkpoint_id.c.id)]
        ).select_from(checkpoint_id)
        id_ = 1
        with self.connect() as conn:
            for max_id, in conn.execute(s).fetchall():
                if max_id is not None and max_id >= id_:
                    id_ = max_id + 1
            for dao in daos:
                checkpoint = {
                    'id': id_,
                    'time': get_current_time_string(),
                    'event': event
                }
                dao.to_insert[checkpoint_id.name].append(
                    [checkpoint_id.insert(), checkpoint])
            for table, checkpoint_table in [
                (suite_params, suite_params_checkpoints),
                (broadcast_states, broadcast_states_checkpoints),
                (task_pool, task_pool_checkpoints)
            ]:
                for row in conn.execute(table.select()):
                    for dao in daos:
                        insert_values = {
                            'id': id_
                        }
                        insert_values.update(row)
                        dao.to_insert[checkpoint_table.name].append(
                            [checkpoint_table.insert(), insert_values])

    def get_cycle_point_format(self):
        """Get the ``suite_params`` cycle point format."""
        with self.connect() as conn:
            s = Select([
                suite_params.c.value
            ]).where(suite_params.c.key == 'cycle_point_format')
            row = conn.execute(s).fetchone()
            if row:
                return row[0]
            return None

    def find_task_outputs(
            self,
            task,
            cycle,
            state_lookup,
            status=None):
        mask = "outputs"
        return self._find_task_states_or_outputs(
            table=task_outputs,
            mask=mask,
            task=task,
            cycle=cycle,
            state_lookup=state_lookup,
            status=status
        )

    def find_task_states(
            self,
            mask,
            task,
            cycle,
            state_lookup,
            status=None):
        if mask is None:
            mask = "name, cycle, status"
        return self._find_task_states_or_outputs(
            table=task_states,
            mask=mask,
            task=task,
            cycle=cycle,
            state_lookup=state_lookup,
            status=status
        )

    def _find_task_states_or_outputs(
            self,
            *,
            table,
            mask,
            task,
            cycle,
            state_lookup,
            status):
        s = Select([
            table.c[column.strip()] for column in mask.split(",")
        ])
        if task is not None:
            s = s.where(table.c.name == task)
        if cycle is not None:
            s = s.where(table.c.cycle == cycle)
        if status:
            s = s.where(
                or_(*[
                    table.c.status == state for state in state_lookup
                ])
            )
        res = []
        with self.connect() as conn:
            for row in conn.execute(s).fetchall():
                if not all(v is None for v in row):
                    res.append(list(row))
        return res

    def is_sqlite(self) -> bool:
        return self.engine.dialect.name == 'sqlite'

    def vacuum(self):
        """Vacuum to the database if the DB currently used supports it."""
        if self.is_sqlite():
            return self.connect().execute("VACUUM")

    def remove_columns(self, table: str, to_drop: List[str]):
        schema = self.conn.execute(f'''
            PRAGMA table_info({table})
        ''').fetchall()

        # get list of columns to keep
        new_cols = [
            name
            for _, name, *_ in schema
            if name not in to_drop
        ]
        # copy table
        self.conn.execute(
            rf'''
                CREATE TABLE {table}_new AS
                SELECT {', '.join(new_cols)}
                FROM {table}
            '''
        )

        # remove original
        self.conn.execute(
            rf'''
                DROP TABLE {table}
            '''
        )

        # copy table
        self.conn.execute(
            rf'''
                CREATE TABLE {table} AS
                SELECT {', '.join(new_cols)}
                FROM {table}_new
            '''
        )
        # done

    def upgrade_is_held(self):
        """Upgrade hold_swap => is_held.

        * Add a is_held column.
        * Set status and is_held as per the new schema.
        * Set the swap_hold values to None
          (because sqlite3 does not support DROP COLUMN)

        From:
            cylc<8
        To:
            cylc>=8
        PR:
            #3230

        Returns:
            bool - True if upgrade performed, False if upgrade skipped.

        """
        # FIXME: Alembic? See JupyterHub... it seems to be able to workaround
        #        drop limitation with sqlite, and would support other DBs.
        conn = self.connect()

        # check if upgrade required
        schema = conn.execute(rf'PRAGMA table_info({task_pool.name})')
        for _, name, *_ in schema:
            if name == 'is_held':
                LOG.debug('is_held column present - skipping db upgrade')
                conn.close()
                return False

        trans = conn.begin()
        # perform upgrade
        for table in [task_pool.name, task_pool_checkpoints.name]:
            LOG.info('Upgrade hold_swap => is_held in %s', table)
            conn.execute(
                rf'''
                    ALTER TABLE
                        {table}
                    ADD COLUMN
                        is_held BOOL
                '''
            )
            for cycle, name, status, hold_swap in conn.execute(
                rf'''
                    SELECT
                        cycle, name, status, hold_swap
                    FROM
                        {table}
            '''):
                if status == 'held':
                    new_status = hold_swap
                    is_held = True
                elif hold_swap == 'held':
                    new_status = status
                    is_held = True
                else:
                    new_status = status
                    is_held = False
                conn.execute(
                    rf'''
                        UPDATE
                            {table}
                        SET
                            status=?,
                            is_held=?,
                            hold_swap=?
                        WHERE
                            cycle==?
                            AND name==?
                    ''',
                    (new_status, is_held, None, cycle, name)
                )
            self.remove_columns(table, ['hold_swap'])
        trans.commit()
        conn.close()
        return True

    def upgrade_to_platforms(self):
        """upgrade [job]batch system and [remote]host to platform

        * Add 'platform' and 'user' columns to table task_jobs.
        * Remove 'user_at_host' and 'batch_sys_name' columns


        Returns:
            bool - True if upgrade performed, False if upgrade skipped.
        """
        conn = self.connect()

        # check if upgrade required
        schema = conn.execute(rf'PRAGMA table_info({task_jobs.name})')
        for _, name, *_ in schema:
            if name == 'platform':
                LOG.debug('platform column present - skipping db upgrade')
                conn.close()
                return False

        trans = conn.begin()
        # Perform upgrade:
        table = task_jobs.name
        LOG.info('Upgrade to Cylc 8 platforms syntax')
        conn.execute(
            rf'''
                ALTER TABLE
                    {table}
                ADD COLUMN
                    user TEXT
            '''
        )
        conn.execute(
            rf'''
                ALTER TABLE
                    {table}
                ADD COLUMN
                    platform TEXT
            '''
        )
        job_platforms = glbl_cfg(cached=False).get(['job platforms'])
        for cycle, name, user_at_host, batch_system in conn.execute(rf'''
                SELECT
                    cycle, name, user_at_host, batch_system
                FROM
                    {table}
        '''):
            match = re.match(r"(?P<user>\S+)@(?P<host>\S+)", user_at_host)
            if match:
                user = match.group('user')
                host = match.group('host')
            else:
                user = ''
                host = user_at_host
            platform = reverse_lookup(
                job_platforms,
                {'batch system': batch_system},
                {'host': host}
            )
            conn.execute(
                rf'''
                    UPDATE
                        {table}
                    SET
                        user=?,
                        platform=?
                    WHERE
                        cycle==?
                        AND name==?
                ''',
                (user, platform, cycle, name)
            )
        trans.commit()
        conn.close()
        return True


__all__ = [
    "CylcSuiteDAO",
    "broadcast_events",
    "broadcast_states",
    "broadcast_states_checkpoints",
    "inheritance",
    "suite_params",
    "suite_params_checkpoints",
    "suite_template_vars",
    "task_jobs",
    "task_events",
    "task_action_timers",
    "checkpoint_id",
    "task_late_flags",
    "task_outputs",
    "task_pool",
    "task_pool_checkpoints",
    "task_states",
    "task_timeout_timers",
    "xtriggers"
]
