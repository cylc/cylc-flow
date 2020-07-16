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
# Test restarting a suite with pre-initial cycle dependencies
. "$(dirname "$0")/test_header"
set_test_number 5
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
RUND="$(cylc get-global-config --print-run-dir)"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" cylc run --debug --no-detach "${SUITE_NAME}"
sqlite3 "${RUND}/${SUITE_NAME}/log/db" \
    'SELECT name, cycle, status FROM task_pool ORDER BY name, cycle' \
    >'mid-state'
cmp_ok 'mid-state' <<"__OUT__"
p1|20100808T0000Z|running
__OUT__

suite_run_ok "${TEST_NAME_BASE}-restart" cylc restart --debug --no-detach "${SUITE_NAME}"
sqlite3 "${RUND}/${SUITE_NAME}/log/db" \
    'SELECT name, cycle, status FROM task_states ORDER BY name, cycle' \
    >'final-state'
contains_ok 'final-state' "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/ref-state"

purge_suite "${SUITE_NAME}"
exit
