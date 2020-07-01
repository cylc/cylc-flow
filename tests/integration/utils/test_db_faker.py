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
"""Tests to ensure the tests are working - very meta.

https://github.com/cylc/cylc-flow/pull/2740#discussion_r206086008

"""

from .db_faker import (
    Task,
    Job,
    JOB_STATUS_MAP,
    _mock_jobs,
    _mock_submit_num
)


def job(name, cycle, submit_num, status, **kwargs):
    """Expands the "status" field to make tests easier to write."""
    return Job(**{
        'name': name,
        'cycle': cycle,
        'submit_num': submit_num,
        'status': status,
        **kwargs,
        **JOB_STATUS_MAP[status]
    })


def test_mock_jobs_no_jobs():
    """It should guess sensible jobs if we don't specify any."""
    assert _mock_jobs([
        Task('foo', '1', 'waiting', submit_num=0)
    ]) == []

    assert _mock_jobs([
        Task('foo', '1', 'waiting', submit_num=1)
    ]) == []

    assert _mock_jobs([
        Task('foo', '1', 'running', submit_num=1)
    ]) == [
        job('foo', '1', 1, 'running')
    ]

    assert _mock_jobs([
        Task('foo', '1', 'running', submit_num=2)
    ]) == [
        job('foo', '1', 1, 'failed'),
        job('foo', '1', 2, 'running')
    ]


def test_mock_jobs_job_list():
    """It should mock sensile jobs from the provided info."""
    assert _mock_jobs([
        Task('foo', '1', 'waiting', jobs=[])
    ]) == []

    assert _mock_jobs([
        Task('foo', '1', 'waiting', jobs=[
            Job('succeeded')
        ])
    ]) == [
        job('foo', '1', 1, 'succeeded')
    ]

    assert _mock_jobs([
        Task('foo', '1', 'waiting', jobs=[
            Job('submit-failed'),
            Job('submitted'),
            Job('running'),
            Job('succeeded')
        ])
    ]) == [
        job('foo', '1', 1, 'submit-failed'),
        job('foo', '1', 2, 'submitted'),
        job('foo', '1', 3, 'running'),
        job('foo', '1', 4, 'succeeded')
    ]


def test_mock_submit_num_no_jobs():
    """It should work out the submit number if not provided."""
    assert _mock_submit_num([
        Task('foo', '1', 'waiting')
    ]) == [
        Task('foo', '1', 'waiting')
    ]

    assert _mock_submit_num([
        Task('foo', '1', 'running')
    ]) == [
        Task('foo', '1', 'running', submit_num=1)
    ]


def test_mock_submit_num_job_list():
    """It should work out the submit number if not provided."""
    assert _mock_submit_num([
        Task('foo', '1', 'waiting', jobs=None)
    ]) == [
        Task('foo', '1', 'waiting')
    ]

    jobs = [Job('foo', '1', 1, 'failed')]
    assert _mock_submit_num([
        Task('foo', '1', 'waiting', jobs)
    ]) == [
        Task('foo', '1', 'waiting', jobs, submit_num=1)
    ]

    jobs = [
        Job('foo', '1', 1, 'failed'),
        Job('foo', '1', 1, 'failed'),
    ]
    assert _mock_submit_num([
        Task('foo', '1', 'waiting', jobs)
    ]) == [
        Task('foo', '1', 'waiting', jobs, submit_num=2)
    ]
