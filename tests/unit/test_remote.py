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
"""Test the cylc.flow.remote module."""

import os

import pytest

from cylc.flow.remote import (
    run_cmd, construct_rsync_over_ssh_cmd, construct_ssh_cmd
)
import cylc.flow


def test_run_cmd_stdin_str():
    """Test passing stdin as a string."""
    proc = run_cmd(
        ['sed', 's/foo/bar/'],
        stdin_str='1foo2',
        capture_process=True
    )
    assert [s.strip() for s in proc.communicate()] == [
        '1bar2',
        ''
    ]


def test_run_cmd_stdin_file(tmp_path):
    """Test passing stdin as a file."""
    tmp_path = tmp_path / 'stdin'
    with tmp_path.open('w+') as tmp_file:
        tmp_file.write('1foo2')
    tmp_file = tmp_path.open('rb')
    proc = run_cmd(
        ['sed', 's/foo/bar/'],
        stdin=tmp_file,
        capture_process=True
    )
    assert [s.strip() for s in proc.communicate()] == [
        '1bar2',
        ''
    ]


def test_construct_rsync_over_ssh_cmd():
    """Function against known good output.
    """
    cmd, host = construct_rsync_over_ssh_cmd(
        '/foo',
        '/bar',
        {
            'rsync command': 'rsync command',
            'hosts': ['miklegard'],
            'ssh command': 'strange_ssh',
            'selection': {'method': 'definition order'},
            'name': 'testplat'
        }
    )
    assert host == 'miklegard'
    assert cmd == [
        'rsync',
        'command',
        '--delete',
        '--rsh=strange_ssh',
        '--include=/.service/',
        '--include=/.service/server.key',
        '-a',
        '--checksum',
        '--out-format=%o %n%L',
        '--no-t',
        '--exclude=log',
        '--exclude=share',
        '--exclude=work',
        '--include=/ana/***',
        '--include=/app/***',
        '--include=/bin/***',
        '--include=/etc/***',
        '--include=/lib/***',
        '--exclude=*',
        '/foo/',
        'miklegard:/bar/',
    ]


def test_construct_ssh_cmd_forward_env(monkeypatch: pytest.MonkeyPatch):
    """ Test for 'ssh forward environment variables'
    """
    # Clear CYLC_* env vars as these will show up in the command
    for env_var in os.environ:
        if env_var.startswith('CYLC'):
            monkeypatch.delenv(env_var)

    host = 'example.com'
    config = {
        'ssh command': 'ssh',
        'use login shell': None,
        'cylc path': None,
        'ssh forward environment variables': ['FOO', 'BAZ'],
    }

    # Variable isn't set, no change to command
    expect = [
        'ssh',
        host,
        'env',
        f'CYLC_VERSION={cylc.flow.__version__}',
        'cylc',
        'play',
    ]
    cmd = construct_ssh_cmd(['play'], config, host)
    assert cmd == expect

    # Variable is set, appears in `env` list
    monkeypatch.setenv('FOO', 'BAR')
    expect = [
        'ssh',
        host,
        'env',
        f'CYLC_VERSION={cylc.flow.__version__}',
        'FOO=BAR',
        'cylc',
        'play',
    ]
    cmd = construct_ssh_cmd(['play'], config, host)
    assert cmd == expect
