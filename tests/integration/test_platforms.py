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
"""Integration testing for platforms functionality.
"""

from contextlib import suppress

from cylc.flow.exceptions import NoPlatformsError
from cylc.flow.task_job_logs import get_task_job_activity_log


async def test_prep_submit_task_tries_multiple_platforms(
    flow, scheduler, run, mock_glbl_cfg, monkeypatch, tmp_path
):
    """Preparation tries multiple platforms within a group if the
    task platform setting matches a group, and that after all platforms
    have been tried that the hosts matching that platform group are
    cleared.
    """
    global_conf = '''
        [platforms]
            [[myplatform]]
                hosts = broken
            [[anotherbad]]
                hosts = broken2
        [platform groups]
            [[mygroup]]
                platforms = myplatform, anotherbad'''
    mock_glbl_cfg('cylc.flow.platforms.glbl_cfg', global_conf)

    wid = flow({
        "scheduling": {"graph": {"R1": "foo"}},
        "runtime": {"foo": {"platform": "mygroup"}}
    })
    schd = scheduler(wid, paused_start=False, run_mode='live')
    async with run(schd):
        itask = schd.pool.get_tasks()[0]
        itask.submit_num = 1
        schd.task_job_mgr.bad_hosts = {'broken', 'broken2'}
        res = schd.task_job_mgr._prep_submit_task_job(schd.workflow, itask)
        assert res is False
        # ensure the bad hosts have been cleared
        assert not schd.task_job_mgr.bad_hosts
