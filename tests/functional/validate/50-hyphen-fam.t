#!/usr/bin/env bash
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
# Test validation of task name with a XXX-FAM pattern.
# See issue cylc/cylc-flow#1778 where validation of the following valid suite failed.
. "$(dirname "$0")/test_header"
set_test_number 2

cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    [[graph]]
        R1 = "baz-foo => bar"
[runtime]
    [[foo]]
    [[bar, baz-foo]]
        inherit = foo
__SUITE_RC__

run_ok "${TEST_NAME_BASE}" cylc validate 'suite.rc'

cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    [[graph]]
        R1 = "foo-baz => bar"
[runtime]
    [[foo]]
    [[bar, foo-baz]]
        inherit = foo
__SUITE_RC__

run_ok "${TEST_NAME_BASE}" cylc validate 'suite.rc'
exit
