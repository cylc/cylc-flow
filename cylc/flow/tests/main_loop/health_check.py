# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
from unittest.mock import Mock

import pytest

from cylc.flow.exceptions import CylcError
from cylc.flow.main_loop.health_check import (
    _check_suite_run_dir,
    _check_contact_file
)


def test_check_suite_run_dir():
    """Ensure a missing suite run dir raises an CylcError."""
    sched = Mock(suite_run_dir='/a/b/c/d/e')
    with pytest.raises(CylcError):
        _check_suite_run_dir(sched)


def test_check_contact_file_data(monkeypatch):
    """Ensure differing contact file data raises CylcError."""
    contact_data = {
        'a': 'beef',
        'b': 2
    }
    sched = Mock(
        suite='foo',
        contact_data=dict(contact_data)
    )
    monkeypatch.setattr(
        'cylc.flow.main_loop.health_check.suite_files.load_contact_file',
        lambda x: dict(contact_data)
    )
    # pass
    _check_contact_file(sched)

    # fail
    contact_data['a'] = 'wellington'
    with pytest.raises(CylcError):
        _check_contact_file(sched)


def test_check_contact_file_io(monkeypatch):
    """Ensure IOError retrieving the contact file raises CylcError."""
    sched = Mock(suite='foo')

    def whoopsie(*_):
        raise IOError('')

    monkeypatch.setattr(
        'cylc.flow.main_loop.health_check.suite_files.load_contact_file',
        whoopsie
    )
    with pytest.raises(CylcError):
        _check_contact_file(sched)
