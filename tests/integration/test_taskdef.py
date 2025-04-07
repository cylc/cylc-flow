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
