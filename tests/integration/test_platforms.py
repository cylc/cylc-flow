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


async def test_foo(flow, scheduler, run, mock_glbl_cfg, validate, monkeypatch):
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
        "scheduling": {
            "graph": {
                "R1": "foo"
            }
        },
        "runtime": {
            "root": {},
            "print-config": {
                "script": "cylc config"
            },
            "foo": {
                "script": "sleep 10",
                "platform": "mygroup",
                "submission retry delays": '3*PT5S'
            }
        }
    })
    validate(wid)
    schd = scheduler(wid, paused_start=False, run_mode='live')
    async with run(schd) as log:
        itask = schd.pool.get_tasks()[0]

        # Avoid breaking on trying to create log file path:
        schd.task_job_mgr._create_job_log_path = lambda *_: None
        schd.task_job_mgr.bad_hosts = {'broken', 'broken2'}
        res = schd.task_job_mgr._prep_submit_task_job(schd.workflow, itask)
        assert res is True
        assert not schd.task_job_mgr.bad_hosts
