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

from copy import copy
import pytest

from cylc.flow import ID_DELIM
from cylc.flow.job_pool import JOB_STATUSES_ALL
from cylc.flow.wallclock import get_current_time_string


def job_config(schd):
    return {
        'owner': schd.owner,
        'host': 'commet',
        'submit_num': 3,
        'task_id': 'foo.20130808T00',
        'job_runner_name': 'background',
        'env-script': None,
        'err-script': None,
        'exit-script': None,
        'execution_time_limit': None,
        'init-script': None,
        'post-script': None,
        'pre-script': None,
        'script': 'sleep 5; echo "I come in peace"',
        'work_d': None,
        'directives': {},
        'environment': {},
        'param_var': {},
        'logfiles': [],
        'platform': {'name': 'platform'},
    }


@pytest.fixture
def job_db_row():
    return [
        '20130808T00',
        'foo',
        'running',
        3,
        '2020-04-03T13:40:18+13:00',
        '2020-04-03T13:40:20+13:00',
        '2020-04-03T13:40:30+13:00',
        'background',
        '20542',
        'localhost',
    ]


@pytest.fixture
@pytest.mark.asyncio
async def myflow(flow, scheduler):
    reg = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo'
            }
        }
    })
    schd = scheduler(reg)
    await schd.install()
    await schd.initialise()
    await schd.configure()
    return schd


def ext_id(schd):
    return (
        f'{schd.owner}{ID_DELIM}{schd.suite}{ID_DELIM}'
        f'20130808T00{ID_DELIM}foo{ID_DELIM}3'
    )


def int_id(_):
    return '20130808T00/foo/03'


def test_insert_job(myflow):
    """Test method that adds a new job to the pool."""
    assert len(myflow.job_pool.added) == 0
    myflow.job_pool.insert_job(job_config(myflow))
    assert len(myflow.job_pool.added) == 1
    assert ext_id(myflow) in myflow.job_pool.added


def test_insert_db_job(myflow, job_db_row):
    """Test method that adds a new job to the pool."""
    assert len(myflow.job_pool.added) == 0
    myflow.job_pool.insert_db_job(0, job_db_row)
    assert len(myflow.job_pool.added) == 1
    assert ext_id(myflow) in myflow.job_pool.added


def test_add_job_msg(myflow):
    """Test method adding messages to job element."""
    myflow.job_pool.insert_job(job_config(myflow))
    job_added = myflow.job_pool.added[ext_id(myflow)]
    assert len(job_added.messages) == 0
    myflow.job_pool.add_job_msg(int_id(myflow), 'The Atomic Age')
    job_updated = myflow.job_pool.updated[ext_id(myflow)]
    assert len(job_updated.messages) == 1


def test_reload_deltas(myflow):
    """Test method reinstatiating job pool on reload"""
    assert myflow.job_pool.updates_pending is False
    myflow.job_pool.insert_job(job_config(myflow))
    myflow.job_pool.pool = {e.id: e for e in myflow.job_pool.added.values()}
    myflow.job_pool.reload_deltas()
    assert myflow.job_pool.updates_pending


def test_remove_job(myflow):
    """Test method removing a job from the pool via internal job id."""
    myflow.job_pool.insert_job(job_config(myflow))
    pruned = myflow.job_pool.deltas.pruned
    assert len(pruned) == 0
    myflow.job_pool.remove_job('NotJobID')
    assert len(pruned) == 0
    myflow.job_pool.remove_job(int_id(myflow))
    assert len(pruned) == 1


def test_remove_task_jobs(myflow):
    """Test method removing jobs from the pool via internal task ID."""
    myflow.job_pool.insert_job(job_config(myflow))
    pruned = myflow.job_pool.deltas.pruned
    assert len(pruned) == 0
    myflow.job_pool.remove_task_jobs('NotTaskID')
    assert len(pruned) == 0
    task_id = myflow.job_pool.added[ext_id(myflow)].task_proxy
    myflow.job_pool.remove_task_jobs(task_id)
    assert len(pruned) == 1


def test_set_job_attr(myflow):
    """Test method setting job attribute value."""
    myflow.job_pool.insert_job(job_config(myflow))
    job_added = myflow.job_pool.added[ext_id(myflow)]
    myflow.job_pool.set_job_attr(int_id(myflow), 'exit_script', 'rm -v *')
    assert job_added.exit_script != (
        myflow.job_pool.updated[ext_id(myflow)].exit_script
    )


def test_set_job_state(myflow):
    """Test method setting the job state."""
    myflow.job_pool.insert_job(job_config(myflow))
    job_added = myflow.job_pool.added[ext_id(myflow)]
    myflow.job_pool.set_job_state(int_id(myflow), JOB_STATUSES_ALL[1])
    job_updated = myflow.job_pool.updated[ext_id(myflow)]
    state_two = copy(job_updated.state)
    assert job_added.state != state_two
    myflow.job_pool.set_job_state(int_id(myflow), JOB_STATUSES_ALL[-1])
    assert state_two != job_updated.state


def test_set_job_time(myflow):
    """Test method setting event time."""
    event_time = get_current_time_string()
    myflow.job_pool.insert_job(job_config(myflow))
    job_added = myflow.job_pool.added[ext_id(myflow)]
    myflow.job_pool.set_job_time(int_id(myflow), 'submitted', event_time)
    job_updated = myflow.job_pool.updated[ext_id(myflow)]
    with pytest.raises(ValueError):
        job_updated.HasField('jumped_time')
    assert job_added.submitted_time != job_updated.submitted_time


def test_parse_job_item(myflow):
    """Test internal id parsing method."""
    point, name, sub_num = myflow.job_pool.parse_job_item(int_id(myflow))
    tpoint, tname, tsub_num = int_id(myflow).split('/', 2)
    assert (point, name, sub_num) == (tpoint, tname, int(tsub_num))
    tpoint, tname, tsub_num = myflow.job_pool.parse_job_item(
        f'{point}/{name}')
    assert name, None == (point, (tpoint, tname, tsub_num))
    tpoint, tname, tsub_num = myflow.job_pool.parse_job_item(
        f'{name}.{point}.{sub_num}')
    assert name, sub_num == (point, (tpoint, tname, tsub_num))
    tpoint, tname, tsub_num = myflow.job_pool.parse_job_item(
        f'{name}.{point}.NotNumber')
    assert name, None == (point, (tpoint, tname, tsub_num))
    tpoint, tname, tsub_num = myflow.job_pool.parse_job_item(
        f'{name}.{point}')
    assert name, None == (point, (tpoint, tname, tsub_num))
    tpoint, tname, tsub_num = myflow.job_pool.parse_job_item(
        f'{name}')
    assert name, None == (None, (tpoint, tname, tsub_num))
