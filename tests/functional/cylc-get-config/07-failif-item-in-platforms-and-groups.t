#!/usr/bin/env bash
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
#-------------------------------------------------------------------------------
# Test that Platforms and Platform Groups return an error listing items
# defined in both.
# Not having additional tests for cases with no overlap or platforms only
# becuase other tests will fail.
# Not testing for platform groups only because the really should never happen.

. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4

create_test_global_config '' '''
[platforms]
    [[Thomas]]
    [[Percy]]
    [[Edward]]
    [[Skarloey]]
[platform groups]
    [[Thomas]]
    [[Percy]]
    [[Gordon]]
    [[Rhenas]]
'''

run_fail "${TEST_NAME_BASE}" cylc config
grep_ok "GlobalConfigError" "${TEST_NAME_BASE}.stderr"
grep_ok "\* Thomas" "${TEST_NAME_BASE}.stderr"
grep_ok "\* Percy" "${TEST_NAME_BASE}.stderr"



exit
