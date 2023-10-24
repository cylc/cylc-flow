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

import os
import sys
from types import SimpleNamespace
from typing import Callable
from unittest.mock import Mock

import pytest

from cylc.flow.scripts.cylc import iter_commands, pythonpath_manip

from ..conftest import MonkeyMock


@pytest.fixture
def mock_entry_points(monkeypatch: pytest.MonkeyPatch):
    """Mock a range of entry points."""
    def _load_fail(*args, **kwargs):
        raise ModuleNotFoundError('foo')

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
                load=_resolve_ok,
                extras=[],
                dist=SimpleNamespace(name='a'),
            ),
            # an entry point with optional dependencies missing:
            'missing': SimpleNamespace(
                name='missing',
                module_name='not.a.python.module',  # force an import error
                load=_load_fail,
                extras=[],
                dist=SimpleNamespace(name='foo'),
            ),
        }
        if include_bad:
            # an entry point with non-optional dependencies unexpectedly
            # missing:
            commands['bad'] = SimpleNamespace(
                name='bad',
                module_name='not.a.python.module',
                load=_load_fail,
                require=_require_ok,
                extras=[],
                dist=SimpleNamespace(name='d'),
            )
        monkeypatch.setattr('cylc.flow.scripts.cylc.COMMANDS', commands)

    return _mocked_entry_points


def test_iter_commands(mock_entry_points):
    """Test listing commands works ok.

    It should exclude commands with missing optional dependencies.
    """
    mock_entry_points()
    commands = list(iter_commands())
    assert [i[0] for i in commands] == ['good']


def test_iter_commands_bad(mock_entry_points):
    """Test listing commands doesn't fail on import error."""
    mock_entry_points(include_bad=True)
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
        '"cylc missing" requires "foo"\n\nModuleNotFoundError: foo'
    )

    # the "bad" entry point should log an error
    execute_cmd('bad')
    capexit.assert_any_call(1)

    stderr = capsys.readouterr().err.strip()
    assert '"cylc bad" requires "d"' in stderr
    assert 'ModuleNotFoundError: foo' in stderr


def test_pythonpath_manip(monkeypatch):
    """pythonpath_manip removes items in PYTHONPATH from sys.path

    and adds items from CYLC_PYTHONPATH
    """
    # If PYTHONPATH is set...
    monkeypatch.setenv('PYTHONPATH', '/remove-from-sys.path')
    monkeypatch.setattr('sys.path', ['/leave-alone', '/remove-from-sys.path'])
    pythonpath_manip()
    # ... we don't change PYTHONPATH
    assert os.environ['PYTHONPATH'] == '/remove-from-sys.path'
    # ... but we do remove PYTHONPATH items from sys.path, and don't remove
    # items there not in PYTHONPATH
    assert sys.path == ['/leave-alone']

    # If CYLC_PYTHONPATH is set we retrieve its contents and
    # add them to the sys.path:
    monkeypatch.setenv('CYLC_PYTHONPATH', '/add-to-sys.path')
    pythonpath_manip()
    assert sys.path == ['/add-to-sys.path', '/leave-alone']
