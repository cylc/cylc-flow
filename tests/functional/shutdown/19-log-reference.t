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
# Test suite shuts down with reference log, specifically that there is no
# issue in the shutdown method when the --reference-log option is used.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    [[events]]
        abort on inactivity = True
        inactivity = PT3M
[scheduling]
    [[graph]]
        R1 = t1
[runtime]
    [[t1]]
        script = true
__SUITERC__
#-------------------------------------------------------------------------------
suite_run_ok "${TEST_NAME_BASE}-run-reflog" \
    cylc run --debug --no-detach --reference-log "${SUITE_NAME}"
exists_ok 'reference.log'
suite_run_ok "${TEST_NAME_BASE}-run-reftest" \
    cylc run --debug --no-detach --reference-test "${SUITE_NAME}"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
