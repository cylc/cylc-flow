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

from unittest import main
from copy import copy, deepcopy

from cylc.flow import LOG
from cylc.flow.job_pool import JobPool, JOB_STATUSES_ALL
from cylc.flow.data_store_mgr import ID_DELIM
from cylc.flow.tests.util import CylcWorkflowTestCase, create_task_proxy
from cylc.flow.wallclock import get_current_time_string


JOB_CONFIG = {
    'owner': '',
    'host': 'commet',
    'submit_num': 3,
    'task_id': 'foo.20130808T00',
    'batch_system_name': 'background',
    'env-script': None,
    'err-script': None,
    'exit-script': None,
    'execution_time_limit': None,
    'init-script': None,
    'post-script': None,
    'pre-script': None,
    'script': 'sleep 5; echo "I come in peace"',
    'work_d': None,
    'batch_system_conf': {},
    'directives': {},
    'environment': {},
    'param_env_tmpl': {},
    'param_var': {},
    'logfiles': [],
}

JOB_DB_ROW = [
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


class TestJobPool(CylcWorkflowTestCase):

    suite_name = "five"
    suiterc = """
[meta]
    title = "Inter-cycle dependence + a cold-start task"
[cylc]
    UTC mode = True
[scheduling]
    #runahead limit = 120
    initial cycle point = 20130808T00
    final cycle point = 20130812T00
    [[graph]]
        R1 = "prep => foo"
        PT12H = "foo[-PT12H] => foo => bar"
[visualization]
    initial cycle point = 20130808T00
    final cycle point = 20130808T12
    [[node attributes]]
        foo = "color=red"
        bar = "color=blue"

    """

    def setUp(self) -> None:
        super(TestJobPool, self).setUp()
        self.job_pool = JobPool(self.scheduler)
        self.job_conf = deepcopy(JOB_CONFIG)
        self.job_conf['owner'] = self.scheduler.owner
        self.ext_id = (
            f'{self.scheduler.owner}{ID_DELIM}five{ID_DELIM}'
            f'20130808T00{ID_DELIM}foo{ID_DELIM}3'
        )
        self.int_id = f'20130808T00/foo/03'

    def test_insert_job(self):
        """Test method that adds a new job to the pool."""
        self.assertEqual(0, len(self.job_pool.updates))
        self.job_pool.insert_job(self.job_conf)
        self.assertEqual(1, len(self.job_pool.updates))
        self.assertTrue(self.ext_id in self.job_pool.updates)

    def test_insert_db_job(self):
        """Test method that adds a new job to the pool."""
        self.assertEqual(0, len(self.job_pool.updates))
        self.job_pool.insert_db_job(0, JOB_DB_ROW)
        self.assertEqual(1, len(self.job_pool.updates))
        self.assertTrue(self.ext_id in self.job_pool.updates)

    def test_add_job_msg(self):
        """Test method adding messages to job element."""
        self.job_pool.insert_job(self.job_conf)
        job = self.job_pool.updates[self.ext_id]
        old_stamp = copy(job.stamp)
        self.assertEqual(0, len(job.messages))
        self.job_pool.add_job_msg(self.int_id, 'The Atomic Age')
        self.assertNotEqual(old_stamp, job.stamp)
        self.assertEqual(1, len(job.messages))

    def test_reload_deltas(self):
        """Test method reinstatiating job pool on reload"""
        self.assertFalse(self.job_pool.updates_pending)
        self.job_pool.insert_job(self.job_conf)
        self.job_pool.pool = {e.id: e for e in self.job_pool.updates.values()}
        self.job_pool.reload_deltas()
        self.assertTrue(self.job_pool.updates_pending)

    def test_remove_job(self):
        """Test method removing a job from the pool via internal job id."""
        self.job_pool.insert_job(self.job_conf)
        pruned = self.job_pool.deltas.pruned
        self.assertEqual(0, len(pruned))
        self.job_pool.remove_job('NotJobID')
        self.assertEqual(0, len(pruned))
        self.job_pool.remove_job(self.int_id)
        self.assertEqual(1, len(pruned))

    def test_remove_task_jobs(self):
        """Test method removing jobs from the pool via internal task ID."""
        self.job_pool.insert_job(self.job_conf)
        pruned = self.job_pool.deltas.pruned
        self.assertEqual(0, len(pruned))
        self.job_pool.remove_task_jobs('NotTaskID')
        self.assertEqual(0, len(pruned))
        task_id = self.job_pool.updates[self.ext_id].task_proxy
        self.job_pool.remove_task_jobs(task_id)
        self.assertEqual(1, len(pruned))

    def test_set_job_attr(self):
        """Test method setting job attribute value."""
        self.job_pool.insert_job(self.job_conf)
        job = self.job_pool.updates[self.ext_id]
        old_exit_script = copy(job.exit_script)
        self.assertEqual(old_exit_script, job.exit_script)
        self.job_pool.set_job_attr(self.int_id, 'exit_script', 'rm -v *')
        self.assertNotEqual(old_exit_script, job.exit_script)

    def test_set_job_state(self):
        """Test method setting the job state."""
        self.job_pool.insert_job(self.job_conf)
        job = self.job_pool.updates[self.ext_id]
        old_state = copy(job.state)
        self.job_pool.set_job_state(self.int_id, 'waiting')
        self.assertEqual(old_state, job.state)
        self.job_pool.set_job_state(self.int_id, JOB_STATUSES_ALL[-1])
        self.assertNotEqual(old_state, job.state)

    def test_set_job_time(self):
        """Test method setting event time."""
        event_time = get_current_time_string()
        self.job_pool.insert_job(self.job_conf)
        job = self.job_pool.updates[self.ext_id]
        old_time = copy(job.submitted_time)
        self.assertEqual(old_time, job.submitted_time)
        self.job_pool.set_job_time(self.int_id, 'submitted', event_time)
        self.assertNotEqual(old_time, job.submitted_time)

    def test_parse_job_item(self):
        """Test internal id parsing method."""
        point, name, sub_num = self.job_pool.parse_job_item(self.int_id)
        tpoint, tname, tsub_num = self.int_id.split('/', 2)
        self.assertEqual(
            (point, name, sub_num), (tpoint, tname, int(tsub_num)))
        tpoint, tname, tsub_num = self.job_pool.parse_job_item(
            f'{point}/{name}')
        self.assertEqual((point, name, None), (tpoint, tname, tsub_num))
        tpoint, tname, tsub_num = self.job_pool.parse_job_item(
            f'{name}.{point}.{sub_num}')
        self.assertEqual((point, name, sub_num), (tpoint, tname, tsub_num))
        tpoint, tname, tsub_num = self.job_pool.parse_job_item(
            f'{name}.{point}.NotNumber')
        self.assertEqual((point, name, None), (tpoint, tname, tsub_num))
        tpoint, tname, tsub_num = self.job_pool.parse_job_item(
            f'{name}.{point}')
        self.assertEqual((point, name, None), (tpoint, tname, tsub_num))
        tpoint, tname, tsub_num = self.job_pool.parse_job_item(
            f'{name}')
        self.assertEqual((None, name, None), (tpoint, tname, tsub_num))


if __name__ == '__main__':
    main()
