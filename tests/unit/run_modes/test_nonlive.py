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

from cylc.flow.run_modes.nonlive import mode_validate_checks


def test_mode_validate_checks(monkeypatch, caplog):
    """It warns us if we've set a task config to nonlive mode.

    (And not otherwise)
    """
    taskdefs = {
        f'{run_mode}_task': SimpleNamespace(
            rtconfig={'run mode': run_mode},
            name=f'{run_mode}_task'
        )
        for run_mode
        in ['live', 'workflow', 'dummy', 'simulation', 'skip']
    }

    mode_validate_checks(taskdefs)

    message = caplog.messages[0]

    assert 'skip mode:\n    * skip_task' not in message
    assert 'simulation mode:\n    * simulation_task' in message
    assert 'dummy mode:\n    * dummy_task' in message
    assert ' live mode' not in message   # Avoid matching "non-live mode"
    assert 'workflow mode' not in message
