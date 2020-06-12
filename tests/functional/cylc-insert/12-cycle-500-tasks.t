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
# Test cylc insert command, with wildcard in a task name string
. "$(dirname "$0")/test_header"
set_test_number 4
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}" cylc run --hold "${SUITE_NAME}"
poll_grep_suite_log -F 'Held on start-up'
run_ok "${TEST_NAME_BASE}-insert" cylc insert "${SUITE_NAME}" '2008/*'
poll_grep_suite_log -F 'Command succeeded: insert_tasks'
cylc stop --max-polls=10 --interval=6 "${SUITE_NAME}" 2>'/dev/null'
cut -d' ' -f 2- "${SUITE_RUN_DIR}/log/suite/log" >'trimmed-log'
{
    for I in {001..500}; do
        echo "INFO - [v_i${I}.2008] -submit-num=00, inserted"
    done
    echo "INFO - Command succeeded: insert_tasks(['2008/*'], stop_point_string=None, check_point=True)"
} >'expected-log'
contains_ok 'trimmed-log' 'expected-log'

purge_suite "${SUITE_NAME}"
exit
