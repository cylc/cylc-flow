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

"""Tests for cylc.flow.scripts.validate_reinstall.py
"""

import pytest

from cylc.flow.scripts.validate_reinstall import (
    check_tvars_and_workflow_stopped)


@pytest.mark.parametrize(
    'is_running, tvars, tvars_file, expect',
    [
        (True, [], None, True),
        (True, ['FOO="Bar"'], None, False),
        (True, [], ['bar.txt'], False),
        (True, ['FOO="Bar"'], ['bar.txt'], False),
        (False, [], None, True),
        (False, ['FOO="Bar"'], ['bar.txt'], True),
        (False, [], ['bar.txt'], True),
        (False, ['FOO="Bar"'], ['bar.txt'], True),
    ]
)
def test_check_tvars_and_workflow_stopped(
    caplog, is_running, tvars, tvars_file, expect
):
    """It returns true if workflow is running and tvars or tvars_file is set.
    """
    result = check_tvars_and_workflow_stopped(is_running, tvars, tvars_file)
    assert result == expect
    if expect is False:
        warn = 'can only be changed if'
        assert warn in caplog.records[0].msg
