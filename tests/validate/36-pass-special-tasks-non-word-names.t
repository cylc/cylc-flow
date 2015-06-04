#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
#-------------------------------------------------------------------------------
# Test validation of special tasks names with non-word characters
. "$(dirname "$0")/test_header"
set_test_number 1
cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    initial cycle point = 20200202
    final cycle point = 20300303
    [[special tasks]]
        clock-triggered = t-1, t+1, t%1, t@1
    [[dependencies]]
        [[[P1D]]]
            graph = """
t-1
t+1
t%1
t@1
"""

[runtime]
    [[t-1, t+1, t%1, t@1]]
        script = true
__SUITE_RC__
run_ok "${TEST_NAME_BASE}" cylc validate --strict "${PWD}/suite.rc"
exit
