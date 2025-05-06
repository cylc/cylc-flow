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

from contextlib import contextmanager
from secrets import token_hex
import sqlite3

import pytest

from cylc.flow.exceptions import ServiceFileError
from cylc.flow.scheduler_cli import (
    RunOptions,
    _distribute,
    _version_check,
)

from .conftest import MonkeyMock


@pytest.fixture
def stopped_workflow_db(tmp_path):
    """Returns a workflow DB with the `cylc_version` set to the provided
    string.

    def test_x(stopped_workflow_db):
        db_file = stopped_workflow_db(version)

    """
    def _stopped_workflow_db(version):
        db_file = tmp_path / 'db'
        conn = sqlite3.connect(db_file)
        conn.execute('''
            CREATE TABLE
                workflow_params(key TEXT, value TEXT, PRIMARY KEY(key))
        ''')
        conn.execute(
            '''
                INSERT INTO
                    workflow_params
                VALUES (?, ?)
            ''',
            ('cylc_version', version)
        )
        conn.commit()
        conn.close()
        return db_file

    return _stopped_workflow_db


@pytest.fixture
def set_cylc_version(monkeypatch):
    """Set the cylc.flow.__version__ attribute.

    def test_x(set_cylc_version):
        set_cylc_version('1.2.3')

    """
    def _set_cylc_version(version):
        monkeypatch.setattr(
            'cylc.flow.scheduler_cli.__version__',
            version,
        )
    return _set_cylc_version


@pytest.fixture
def answer(monkeypatch):
    """Answer a `cylc play` CLI prompt.

    def test_x(answer):
        answer(users_response)

    It also adds an assert on the number of times the prompt interface was
    called. 0 if response is None, else 1.

    """
    @contextmanager
    def _answer(response):
        calls = 0

        def prompt(*args, **kwargs):
            nonlocal calls
            calls += 1
            return response

        monkeypatch.setattr(
            'cylc.flow.scheduler_cli.prompt',
            prompt,
        )

        yield

        expected_calls = 1
        if response is None:
            expected_calls = 0
        assert calls == expected_calls

    return _answer


@pytest.fixture
def interactive(monkeypatch):
    monkeypatch.setattr(
        'cylc.flow.scheduler_cli.is_terminal',
        lambda: True,
    )


@pytest.fixture
def non_interactive(monkeypatch):
    monkeypatch.setattr(
        'cylc.flow.scripts.reinstall.is_terminal',
        lambda: False,
    )


@pytest.mark.parametrize(
    'before, after, downgrade, response, outcome', [
        # no change
        ('8.0.0', '8.0.0', False, None, True),
        # upgrading
        ('8.0rc4.dev', '8.0.0', False, None, True),
        ('8.0.0', '8.0.1', False, None, True),
        ('8.0.0', '8.1.0', False, False, False),
        ('8.0.0', '8.1.0', False, True, True),
        ('8.0.0', '9.0.0', False, False, False),
        ('8.0.0', '9.0.0', False, True, True),
        # downgrading
        ('8.1.1', '8.1.0', False, None, False),
        ('8.1.1', '8.1.0', True, None, True),
        ('8.1.0', '8.0.0', False, None, False),
        ('8.1.0', '8.0.0', True, None, True),
        ('8.1.0', '8.0rc4.dev', True, None, True),
        ('9.1.0', '8.0.0', False, None, False),
        ('9.1.0', '8.0.0', True, None, True),
        # truncated versions
        ('8.1.1', '8', False, None, False),
        ('9.1.1', '8', True, None, True),
    ],
)
def test_version_check_interactive(
    stopped_workflow_db,
    set_cylc_version,
    interactive,
    answer,
    before,
    after,
    response,
    downgrade,
    outcome,
):
    """It should check compatibility with the Cylc version of the prior run.

    When workflows are restarted we need to perform some checks to make sure
    it is safe and sensible to restart with this version of Cylc.

    Pytest Params:
        before:
            The Cylc version the workflow ran with previously.
        after:
            The version of Cylc being used to restart the workflow.
        downgrade:
            The --downgrade option of `cylc play`.
        response:
            The user's response the any CLI prompts.
            If `None` it will assert that no prompts were raised.
        outcome:
            The response of _version_check, True means safe to restart.

    """
    db_file = stopped_workflow_db(before)
    set_cylc_version(after)
    with answer(response):
        assert (
            _version_check(
                db_file, RunOptions(downgrade=downgrade)
            )
            is outcome
        )


def test_version_check_interactive_upgrade(
    stopped_workflow_db,
    set_cylc_version,
    interactive,
    answer,
):
    """If a user interactively upgrades, it should set the upgrade option."""
    db_file = stopped_workflow_db('8.0.0')
    set_cylc_version('8.1.0')
    opts = RunOptions()
    assert opts.upgrade is False
    with answer(True):
        assert _version_check(db_file, opts) is True
    assert opts.upgrade is True


def test_version_check_non_interactive(
    stopped_workflow_db,
    set_cylc_version,
    non_interactive,
):
    """It should not prompt in non-interactive mode.

    * The --upgrade argument should permit upgrade.
    * The --downgrade argument should permit downgrade.
    """
    # upgrade
    db_file = stopped_workflow_db('8.0.0')
    set_cylc_version('8.1.0')
    assert _version_check(db_file, RunOptions()) is False
    assert (
        _version_check(db_file, RunOptions(upgrade=True)) is True
    )  # CLI --upgrade

    # downgrade
    db_file.unlink()
    db_file = stopped_workflow_db('8.1.0')
    set_cylc_version('8.0.0')
    assert _version_check(db_file, RunOptions()) is False
    assert (
        _version_check(db_file, RunOptions(downgrade=True)) is True
    )  # CLI --downgrade


def test_version_check_incompat(tmp_path):
    """It should fail for a corrupted or invalid database file."""
    db_file = tmp_path / 'db'  # invalid DB file
    db_file.touch()
    with pytest.raises(ServiceFileError):
        _version_check(db_file, RunOptions())


def test_version_check_no_db(tmp_path):
    """It should pass if there is no DB file (e.g. on workflow first start)."""
    db_file = tmp_path / 'db'  # non-existent file
    assert _version_check(db_file, RunOptions())


@pytest.mark.parametrize(
    'cli_colour, is_terminal, distribute_colour',
    [
        ('never', True, '--color=never'),
        ('auto', True, '--color=always'),
        ('always', True, '--color=always'),
        ('never', False, '--color=never'),
        ('auto', False, '--color=never'),
        ('always', False, '--color=never'),
    ]
)
def test_distribute_colour(
    monkeymock,
    cli_colour,
    is_terminal,
    distribute_colour,
):
    """It should start detached workflows with the correct --colour option.

    The is_terminal test will fail for detached scheduler processes which means
    that the colour formatting will be stripped for startup. This includes
    the Cylc header logo and any warnings/errors raised during config parsing.

    In order to preserver colour formatting we must set the `--colour` arg to
    `always` when we want the detached process to start in colour mode.

    See https://github.com/cylc/cylc-flow/issues/5159
    """
    _is_terminal = monkeymock('cylc.flow.scheduler_cli.is_terminal')
    _is_terminal.return_value = is_terminal
    _cylc_server_cmd = monkeymock('cylc.flow.scheduler_cli.cylc_server_cmd')
    _cylc_server_cmd.return_value = 0
    opts = RunOptions(host='myhost', color=cli_colour)
    with pytest.raises(SystemExit) as excinfo:
        _distribute('foo', 'foo/run1', opts)
    assert excinfo.value.code == 0
    assert distribute_colour in _cylc_server_cmd.call_args[0][0]


def test_distribute_upgrade(
    monkeymock: MonkeyMock, monkeypatch: pytest.MonkeyPatch
):
    """It should start detached workflows with the --upgrade option if the user
    has interactively chosen to upgrade (typed 'y' at prompt).
    """
    monkeypatch.setattr(
        'sys.argv', ['cylc', 'play', 'foo']  # no upgrade option here
    )
    _cylc_server_cmd = monkeymock('cylc.flow.scheduler_cli.cylc_server_cmd')
    _cylc_server_cmd.return_value = 0
    opts = RunOptions(
        host='myhost',
        upgrade=True,  # added by interactive upgrade
    )
    with pytest.raises(SystemExit) as excinfo:
        _distribute('foo', 'foo/run1', opts)
    assert excinfo.value.code == 0
    assert '--upgrade' in _cylc_server_cmd.call_args[0][0]


def test_distribute_invalid_host(
    mock_glbl_cfg, caplog: pytest.LogCaptureFixture
):
    """It handles a socket error when the host is invalid."""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        f'''
            [scheduler]
                [[run hosts]]
                    available = non_exist_{token_hex(4)}
        '''
    )
    with pytest.raises(SystemExit) as excinfo:
        _distribute('foo', 'foo/run1', RunOptions())
    assert excinfo.value.code != 0
    assert len(caplog.records) == 1
    assert caplog.records[0].message.startswith("Host selection failed: ")
