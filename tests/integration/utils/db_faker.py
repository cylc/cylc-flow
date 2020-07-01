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
"""Utility for faking a cylc run database.

This allows us to put suites into strange states without having to
make the series of events leading to that state actually happen.

This allows us to test a whole range of exotic and hard or even impossible to
reproduce states.

These utilities are not intended for direct use by tests.
Use the fixtures provided in the conftest instead.

"""

from collections import namedtuple
import getpass

from cylc.flow.rundb import CylcSuiteDAO
from cylc.flow.task_state import TASK_STATUSES_ORDERED

__all__ = ('fake_db')


UNSET = '*unset*'

TASK_FIELDS = {
    # these fields you must define
    'name': UNSET,
    'cycle': UNSET,
    'status': UNSET,
    # these fields we can guess for you
    'jobs': None,
    'submit_num': None,
    # these fields you need to provide yourself
    # (else you get the defaults)
    'spawned': False,
    'is_held': False,
    'time_created': None,
    'time_updated': None,
}


Task = namedtuple(
    'task',
    tuple(TASK_FIELDS),
    defaults=tuple(
        value
        for value in TASK_FIELDS.values()
        if value != UNSET
    )
)


JOB_FIELDS = {
    # if you set this field we can guess the rest for you
    'status': None,
    # these fields get generated from the task info
    # (but can be overridden)
    'name': None,
    'cycle': None,
    'submit_num': None,
    'try_num': 1,
    # these fields we will try to guess
    # (but you will probably want to override)
    'submit_status': 0,
    'run_status': None,
    'run_signal': None,
    # these fields you need to provide yourself
    # (else you get the defaults)
    'is_manual_submit': False,
    'time_submit': None,
    'time_submit_exit': None,
    'time_run': None,
    'time_run_exit': None,
    'user_at_host': f'{getpass.getuser()}@localhost',
    'batch_sys_name': 'background',
    'batch_sys_job_id': None,
}


Job = namedtuple(
    'job',
    tuple(JOB_FIELDS),
    defaults=tuple(
        value
        for value in JOB_FIELDS.values()
        if value != UNSET
    )
)


JOB_STATUS_MAP = {
    'submitted': {
        'submit_status': 0,
    },
    'submit-failed': {
        'submit_status': -1,
    },
    'running': {
        'submit_status': 0,
    },
    'succeeded': {
        'submit_status': 0,
        'run_status': 0,
        'run_signal': ''
    },
    'failed': {
        'submit_status': 0,
        'run_status': -1,
        'run_signal': 'EXIT'
    },
}


def _task_has_job(status):
    """Return True if a task status should be associated withi a job."""
    return (
        TASK_STATUSES_ORDERED.index(status)
        >= TASK_STATUSES_ORDERED.index('submit-failed')
    )


def _mock_jobs(tasks):
    """Return a list of jobs for the provided tasks."""
    jobs = []
    for task in tasks:
        submit_num = 1
        defaults = {
            'cycle': task.cycle,
            'name': task.name,
            'try_num': 1,
        }
        task_jobs = task.jobs or []
        if task.jobs is None:
            for submit_num in range(1, task.submit_num or 1):
                task_jobs.append(Job('failed'))
            if _task_has_job(task.status):
                task_jobs.append(Job(task.status))
        for job_def in task_jobs:
            defaults['submit_num'] = submit_num
            job_data = {}
            if job_def.status:
                job_data = JOB_STATUS_MAP[job_def.status]
            jobs.append(
                Job(**{
                    'submit_num': submit_num,
                    **job_def._asdict(),
                    **job_data,
                    **defaults,
                })
            )
            submit_num += 1

    return jobs


def _mock_submit_num(tasks):
    """Determine the submit numbers for the provided tasks."""
    for task in list(tasks):
        if task.submit_num is None and task.jobs:
            tasks.remove(task)
            tasks.append(
                Task(**{
                    **task._asdict(),
                    'submit_num': len(task.jobs)
                })
            )
        elif task.submit_num is None and _task_has_job(task.status):
            tasks.remove(task)
            tasks.append(
                Task(**{
                    **task._asdict(),
                    'submit_num': 1
                })
            )
    return tasks


def _insert(conn, table, items):
    """Insert `items` into `table` using `conn`."""
    fields = [
        item[0]
        for item in CylcSuiteDAO.TABLES_ATTRS[table]
    ]
    conn.executemany(
        f'''
            INSERT INTO
                {table} ({','.join(fields)})
            VALUES
                ({','.join(['?'] * len(fields))})
        ''',
        [
            tuple(
                getattr(item, field)
                for field in fields
            )
            for item in items
        ]
    )


def fake_db(tasks, path='db'):
    f"""Fake a Cylc run database inserting the provided tasks.

    Args:
        tasks (list):
            List of Task instances.

            If a task provides a list of jobs they will also be inserted into
            the database.

            Otherwise we will attempt to guess what jobs should be associated
            with a task.
        path (str):
            The path to create the database in.

    See the comments at the top of {__file__} for information about which
    fields must be set and which can be guessed for both tasks and jobs.

    """
    tasks = _mock_submit_num(tasks)
    jobs = _mock_jobs(tasks)
    dao = CylcSuiteDAO(path)
    try:
        _insert(dao.conn, 'task_pool', tasks)
        _insert(dao.conn, 'task_states', tasks)
        _insert(dao.conn, 'task_jobs', jobs)
        dao.conn.commit()
    finally:
        dao.close()
