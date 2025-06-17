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


from cylc.flow.config import WorkflowConfig
from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.scheduler_cli import RunOptions
from cylc.flow.task_outputs import TASK_OUTPUT_SUCCEEDED
from cylc.flow.workflow_files import WorkflowFiles


async def test_almost_self_suicide(flow, scheduler, start):
    """Suicide triggers should not count as upstream tasks when looking
    to spawn parentless tasks.

    https://github.com/cylc/cylc-flow/issues/6594

    For the example under test, pre-requisites for ``!a`` should not be
    considered the same as pre-requisites for ``a``. If the are then then
    is parentless return false for all cases of ``a`` not in the inital cycle
    and subsequent cycles never run.
    """
    wid = flow({
        'scheduler': {'cycle point format': '%Y'},
        'scheduling': {
            'initial cycle point': 1990,
            'final cycle point': 1992,
            'graph': {
                'R1': 'install_cold',
                'P1Y': 'install_cold[^] => a? => b?\nb:fail? => !a?'
            }
        }
    })
    schd = scheduler(wid)
    async with start(schd):
        tasks = [str(t) for t in schd.pool.get_tasks()]
        for task in ['1990/a:waiting', '1991/a:waiting', '1992/a:waiting']:
            assert task in tasks


def test_graph_children(flow):
    """TaskDef.graph_children should not include duplicates.

    https://github.com/cylc/cylc-flow/issues/6619#issuecomment-2668932069
    """
    wid = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo | bar<n> => fin',
            },
        },
        'task parameters': {
            'n': '1..3',
        },
    })
    config = WorkflowConfig(
        wid, get_workflow_run_dir(wid, WorkflowFiles.FLOW_FILE), RunOptions()
    )
    foo = config.taskdefs['foo']
    graph_children = list(foo.graph_children.values())[0]
    assert [name for name, _ in graph_children[TASK_OUTPUT_SUCCEEDED]] == [
        'fin'
    ]
