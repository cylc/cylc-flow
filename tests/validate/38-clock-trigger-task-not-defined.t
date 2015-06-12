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
set_test_number 2
cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    initial cycle point = 20200101
    [[special tasks]]
        clock-triggered = foo(PT0M)
    [[dependencies]]
        [[[T00]]]
            graph = bar
[runtime]
    [[bar]]
        script = true
__SUITE_RC__
run_fail "${TEST_NAME_BASE}" cylc validate --strict "${PWD}/suite.rc"
cmp_ok "${TEST_NAME_BASE}.stderr" <<'__ERR__'
'ERROR: clock-triggered task "foo" is not defined.'
__ERR__
exit
