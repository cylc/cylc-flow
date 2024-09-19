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
"""Unit tests for utilities supporting all nonlive modes
"""

from types import SimpleNamespace

from cylc.flow.run_modes.nonlive import run_mode_validate_checks


def test_run_mode_validate_checks(monkeypatch, caplog):
    """It warns us if we've set a task config to nonlive mode.

    (And not otherwise)

    Point 3 from the skip mode proposal
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-skip-mode.md

    | If the run mode is set to simulation or skip in the workflow
    | configuration, then cylc validate and cylc lint should produce 
    | warning (similar to development features in other languages / systems).
    """
    taskdefs = {
        f'{run_mode}_task': SimpleNamespace(
            rtconfig={'run mode': run_mode},
            name=f'{run_mode}_task'
        )
        for run_mode
        in ['live', 'skip']
    }

    run_mode_validate_checks(taskdefs)

    message = caplog.messages[0]

    assert 'skip mode:\n    * skip_task' in message
    assert ' live mode' not in message   # Avoid matching "non-live mode"
    assert 'workflow mode' not in message
