#!/usr/bin/env python2

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

import os
import pytest

from cylc.review import CylcReviewService

@pytest.mark.parametrize(
    'cylc_8, log_dir, expected',
    [
        pytest.param(
            True, True, True,
            id="True when flow.cylc and log dir"
        ),
        pytest.param(
            True, False, True,
            id="True when flow.cylc and no log dir"
        ),
        pytest.param(
            False, True, True,
            id="True when suite.rc and log dir"
        ),
        pytest.param(
            False, False, False,
            id="False when suite.rc and no log dir"
        ),
        pytest.param(
            None, False, False,
            id="False when no suite.rc and no flow.cylc"
        ),
    ],
)
def test_is_cylc8(cylc_8, log_dir, expected, tmp_path):
    """Check is_cylc8 returns"""
    temp_workflow_dir = str(tmp_path)
    workflow_file = ''
    if cylc_8:
        workflow_file = os.path.join(temp_workflow_dir, 'flow.cylc')
    elif cylc_8 == False:
        workflow_file = os.path.join(temp_workflow_dir, 'suite.rc')
    if log_dir:
        workflow_log_dir = os.path.join(temp_workflow_dir, "log", "scheduler")
        os.makedirs(workflow_log_dir)
    if workflow_file:
        with open(workflow_file, 'w'):
            pass
    assert CylcReviewService.is_cylc8(temp_workflow_dir) == expected
