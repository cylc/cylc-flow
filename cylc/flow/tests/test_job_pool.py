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

import unittest
from copy import copy

from cylc.flow.job_pool import JobPool, JOB_STATUSES_ALL
from cylc.flow.ws_data_mgr import ID_DELIM
from cylc.flow.wallclock import get_current_time_string


JOB_CONFIG = {
    'owner': 'captain',
    'host': 'commet',
    'submit_num': 3,
    'task_id': 'foo.30010101T01',
    'batch_system_name': 'background',
    'env-script': None,
    'err-script': None,
    'exit-script': None,
    'execution_time_limit': None,
    'job_log_dir': '/home/captain/cylc-run/baz/log/job/30010101T01/foo/03',
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


class TestJobPool(unittest.TestCase):

    def setUp(self) -> None:
        super(TestJobPool, self).setUp()
        self.job_pool = JobPool('baz', 'captain')
        self.ext_id = (
            f'captain{ID_DELIM}baz{ID_DELIM}'
            f'30010101T01{ID_DELIM}foo{ID_DELIM}3'
        )
        self.int_id = f'30010101T01/foo/03'

    def test_insert_job(self):
        """Test method that adds a new job to the pool."""
        self.assertEqual(0, len(self.job_pool.pool))
        self.job_pool.insert_job(JOB_CONFIG)
        self.assertEqual(1, len(self.job_pool.pool))
        self.assertTrue(self.ext_id in self.job_pool.pool)

    def test_add_job_msg(self):
        """Test method adding messages to job element."""
        self.job_pool.insert_job(JOB_CONFIG)
        job = self.job_pool.pool[self.ext_id]
        old_stamp = copy(job.stamp)
        self.assertEqual(0, len(job.messages))
        self.job_pool.add_job_msg('NotJobID', 'The Atomic Age')
        self.assertEqual(0, len(job.messages))
        self.job_pool.add_job_msg(self.int_id, 'The Atomic Age')
        self.assertNotEqual(old_stamp, job.stamp)
        self.assertEqual(1, len(job.messages))

    def test_remove_job(self):
        """Test method removing a job from the pool via internal job id."""
        self.job_pool.insert_job(JOB_CONFIG)
        jobs = self.job_pool.pool
        self.assertEqual(1, len(jobs))
        self.job_pool.remove_job('NotJobID')
        self.assertEqual(1, len(jobs))
        self.job_pool.remove_job(self.int_id)
        self.assertEqual(0, len(jobs))

    def test_remove_task_jobs(self):
        """Test method removing jobs from the pool via internal task ID."""
        self.job_pool.insert_job(JOB_CONFIG)
        jobs = self.job_pool.pool
        self.assertEqual(1, len(jobs))
        self.job_pool.remove_task_jobs('NotTaskID')
        self.assertEqual(1, len(jobs))
        task_id = self.job_pool.pool[self.ext_id].task_proxy
        self.job_pool.remove_task_jobs(task_id)
        self.assertEqual(0, len(jobs))

    def test_set_job_attr(self):
        """Test method setting job attribute value."""
        self.job_pool.insert_job(JOB_CONFIG)
        job = self.job_pool.pool[self.ext_id]
        old_exit_script = copy(job.exit_script)
        self.job_pool.set_job_attr(self.int_id, 'leave_scripting', 'rm -v *')
        self.assertEqual(old_exit_script, job.exit_script)
        self.job_pool.set_job_attr(self.int_id, 'exit_script', 10.0)
        self.assertEqual(old_exit_script, job.exit_script)
        self.job_pool.set_job_attr(self.int_id, 'exit_script', 'rm -v *')
        self.assertNotEqual(old_exit_script, job.exit_script)

    def test_set_job_state(self):
        """Test method setting the job state."""
        self.job_pool.insert_job(JOB_CONFIG)
        job = self.job_pool.pool[self.ext_id]
        old_state = copy(job.state)
        self.job_pool.set_job_state(self.int_id, 'waiting')
        self.assertEqual(old_state, job.state)
        self.job_pool.set_job_state('NotJobID', JOB_STATUSES_ALL[0])
        self.assertEqual(old_state, job.state)
        self.job_pool.set_job_state(self.int_id, JOB_STATUSES_ALL[-1])
        self.assertNotEqual(old_state, job.state)

    def test_set_job_time(self):
        """Test method setting event time."""
        event_time = get_current_time_string()
        self.job_pool.insert_job(JOB_CONFIG)
        job = self.job_pool.pool[self.ext_id]
        old_time = copy(job.submitted_time)
        self.job_pool.set_job_time(self.int_id, 'jumped', event_time)
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
    unittest.main()
