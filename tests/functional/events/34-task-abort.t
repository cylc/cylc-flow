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
# Test job abort-with-message and interaction with failed handler.
. "$(dirname "$0")/test_header"
set_test_number 5
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
# Check failed handler only call on last try.
LOG="${SUITE_RUN_DIR}/log/job/1/foo/NN/job-activity.log"
grep "event-handler" "${LOG}" > 'edited-job-activity.log'
cmp_ok 'edited-job-activity.log' <<'__LOG__'
[(('event-handler-00', 'failed'), 2) cmd] echo "!!!FAILED!!!" failed foo.1 2 '"ERROR: rust never sleeps"'
[(('event-handler-00', 'failed'), 2) ret_code] 0
[(('event-handler-00', 'failed'), 2) out] !!!FAILED!!! failed foo.1 2 "ERROR: rust never sleeps"
__LOG__
#-------------------------------------------------------------------------------
# Check job stdout stops at the abort call.
LOG="${SUITE_RUN_DIR}/log/job/1/foo/NN/job.out"
# ...before abort
grep_ok 'ONE' "${LOG}"
# ...after abort
grep_fail 'TWO' "${LOG}"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
