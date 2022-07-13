#!/usr/bin/env python3
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

import pkg_resources
from types import SimpleNamespace
from typing import Callable
from unittest.mock import Mock

import pytest

from cylc.flow.scripts.cylc import iter_commands

from ..conftest import MonkeyMock


@pytest.fixture
def mock_entry_points(monkeypatch: pytest.MonkeyPatch):
    """Mock a range of entry points."""
    def _resolve_fail(*args, **kwargs):
        raise ModuleNotFoundError('foo')

    def _require_fail(*args, **kwargs):
        raise pkg_resources.DistributionNotFound('foo', ['my_extras'])

    def _resolve_ok(*args, **kwargs):
        return Mock()

    def _require_ok(*args, **kwargs):
        return

    def _mocked_entry_points(include_bad: bool = False):
        commands = {
            # an entry point with all dependencies installed:
            'good': SimpleNamespace(
                name='good',
                module_name='os.path',
                resolve=_resolve_ok,
                require=_require_ok,
            ),
            # an entry point with optional dependencies missing:
            'missing': SimpleNamespace(
                name='missing',
                module_name='not.a.python.module',  # force an import error
                resolve=_resolve_fail,
                require=_require_fail,
            ),
            # an entry point with optional dependencies missing, but they
            # are not needed for the core functionality of the entry point:
            'partial': SimpleNamespace(
                name='partial',
                module_name='os.path',
                resolve=_resolve_ok,
                require=_require_fail,
            ),
        }
        if include_bad:
            # an entry point with non-optional dependencies unexpectedly
            # missing:
            commands['bad'] = SimpleNamespace(
                name='bad',
                module_name='not.a.python.module',
                resolve=_resolve_fail,
                require=_require_ok,
            )
        monkeypatch.setattr('cylc.flow.scripts.cylc.COMMANDS', commands)

    return _mocked_entry_points


def test_iter_commands(mock_entry_points):
    """Test listing commands works ok.

    It should exclude commands with missing optional dependencies.
    """
    mock_entry_points()
    commands = list(iter_commands())
    assert [i[0] for i in commands] == ['good', 'partial']


def test_iter_commands_bad(mock_entry_points):
    """Test listing commands fails if there is an unexpected import error."""
    mock_entry_points(include_bad=True)
    with pytest.raises(ModuleNotFoundError):
        list(iter_commands())


def test_execute_cmd(
    mock_entry_points,
    monkeymock: MonkeyMock,
    capsys: pytest.CaptureFixture,
):
    """It should fail with a warning for commands with missing dependencies."""
    # (stop IDEs reporting code as unreachable in this test)
    execute_cmd: Callable
    from cylc.flow.scripts.cylc import execute_cmd

    mock_entry_points(include_bad=True)

    # capture sys.exit calls
    capexit = monkeymock('cylc.flow.scripts.cylc.sys.exit')

    # the "good" entry point should exit 0 (exit with no args)
    execute_cmd('good')
    capexit.assert_called_once_with()
    assert capsys.readouterr().err == ''

    # the "missing" entry point should exit 1 with a warning to stderr
    capexit.reset_mock()
    execute_cmd('missing')
    capexit.assert_any_call(1)
    assert capsys.readouterr().err.strip() == (
        "cylc missing: The 'foo' distribution was not found and is"
        " required by my_extras"
    )

    # the "partial" entry point should exit 0
    capexit.reset_mock()
    execute_cmd('partial')
    capexit.assert_called_once_with()
    assert capsys.readouterr().err == ''

    # the "bad" entry point should raise an exception
    with pytest.raises(ModuleNotFoundError):
        execute_cmd('bad')
