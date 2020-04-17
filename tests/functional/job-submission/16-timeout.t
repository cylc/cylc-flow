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

# Test that job submission kill on timeout results in a failed job submission.

. "$(dirname "$0")/test_header"

skip_darwin 'atrun hard to configure on Mac OS'
set_test_number 4

create_test_globalrc "
process pool timeout = PT10S" ""

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-suite-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"

# egrep -m <num> is stop matching after <num> matches
#       -A <num> is number of lines of context after match
cylc cat-log "${SUITE_NAME}" \
    | grep -E -m 1 -A 2 "ERROR - \[jobs-submit cmd\]" \
       | sed -e 's/^.* \(ERROR\)/\1/' > log

SUITE_LOG_DIR=$(cylc cat-log -m p "${SUITE_NAME}")

cmp_ok log <<__END__
ERROR - [jobs-submit cmd] cylc jobs-submit --debug -- ${SUITE_LOG_DIR%suite/log}job 1/foo/01
	[jobs-submit ret_code] -9
	[jobs-submit err] killed on timeout (PT10S)
__END__

cylc suite-state "${SUITE_NAME}" > suite-state.log

contains_ok suite-state.log << __END__
stopper, 1, succeeded
foo, 1, submit-failed
__END__

purge_suite "${SUITE_NAME}"

