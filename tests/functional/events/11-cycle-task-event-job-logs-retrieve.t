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
# Test remote job logs retrieval, requires compatible version of cylc on remote
# job host.
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
set_test_remote_host
set_test_number 3

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate -s "HOST=${CYLC_TEST_HOST}" "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach -s "HOST=${CYLC_TEST_HOST}" "${SUITE_NAME}"

# There are 2 remote tasks. One with "retrieve job logs = True", one without.
# Only t1 should have job.err and job.out retrieved.

sed "/'job-logs-retrieve'/!d" \
    "${SUITE_RUN_DIR}/log/job/2020-02-02T02:02Z/t"{1,2}'/'{01,02,03}'/job-activity.log' \
    >'edited-activities.log'
cmp_ok 'edited-activities.log' <<__LOG__
[(('job-logs-retrieve', 'retry'), 1) ret_code] 0
[(('job-logs-retrieve', 'retry'), 2) ret_code] 0
[(('job-logs-retrieve', 'succeeded'), 3) ret_code] 0
__LOG__

purge_suite_remote "${CYLC_TEST_HOST}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
