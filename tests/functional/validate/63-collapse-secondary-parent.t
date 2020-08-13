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

# Fail attempt to collapse a non first-parent family in the graph.
# GitHub #2229.

. "$(dirname "$0")/test_header"

set_test_number 2

cat >'suite.rc' <<__SUITE_RC__
[scheduling]
    [[graph]]
        R1 = BAR
[runtime]
    [[root]]
        script = sleep 1
    [[FOO]]
    [[BAR]]
    [[ukv_um_recon_ls]]
        inherit = FOO, BAR
[visualization]
    collapsed families = BAR  # Troublesome setting.
__SUITE_RC__

run_fail "${TEST_NAME_BASE}" cylc validate 'suite.rc'

ERR='SuiteConfigError: \[visualization\]collapsed families: BAR is not a first parent'
grep_ok "$ERR" "${TEST_NAME_BASE}.stderr"

exit
