#!/bin/bash
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
#-------------------------------------------------------------------------------
# Test validation error message on zero-width date-time interval.
# See issue cylc/cylc-flow#1800.
. "$(dirname "$0")/test_header"
set_test_number 2

cat >'suite.rc' <<'__SUITE_RC__'
[cylc]
    UTC mode = True
[scheduling]
    initial cycle point = 2010
    [[graph]]
        P0M = foo  # OOPS! zero-width interval
[runtime]
    [[foo]]
        script = true
__SUITE_RC__

run_fail "${TEST_NAME_BASE}" cylc validate 'suite.rc'
cmp_ok "${TEST_NAME_BASE}.stderr" <<'__ERR__'
SequenceDegenerateError: R/20100101T0000Z/P0Y, point format CCYYMMDDThhmmZ: equal adjacent points: 20100101T0000Z => 20100101T0000Z.
__ERR__

exit
