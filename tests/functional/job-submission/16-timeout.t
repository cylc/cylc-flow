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
# Test that job submission kill on timeout results in a failed job submission.
export REQUIRE_PLATFORM='runner:at comms:tcp'
. "$(dirname "$0")/test_header"
set_test_number 4

create_test_global_config "" "
[scheduler]
    process pool timeout = PT10S
[platforms]
    [[$CYLC_TEST_PLATFORM]]
        job runner command template = sleep 30
"

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-workflow-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

# egrep -m <num> is stop matching after <num> matches
#       -A <num> is number of lines of context after match
cylc cat-log "${WORKFLOW_NAME}" \
    | grep -E -m 1 -A 2 "ERROR - \[jobs-submit cmd\]" \
       | sed -e 's/^.* \(ERROR\)/\1/' > log
WORKFLOW_LOG_DIR=$(cylc cat-log -m p "${WORKFLOW_NAME}" | sed 's/01-start-01\.//')
JOB_LOG_DIR="${WORKFLOW_LOG_DIR%scheduler/log}"
JOB_LOG_DIR="${JOB_LOG_DIR/$HOME/\$HOME}"

DEFAULT_PATHS='--path=/bin --path=/usr/bin --path=/usr/local/bin --path=/sbin --path=/usr/sbin --path=/usr/local/sbin'
cmp_ok log <<__END__
ERROR - [jobs-submit cmd] cylc jobs-submit --debug ${DEFAULT_PATHS} -- '${JOB_LOG_DIR}job' 1/foo/01
    [jobs-submit ret_code] -9
    [jobs-submit err] killed on timeout (PT10S)
__END__

cylc workflow-state "${WORKFLOW_NAME}" > workflow-state.log

# make sure foo submit failed and the stopper ran
contains_ok workflow-state.log << __END__
stopper, 1, succeeded
foo, 1, submit-failed
__END__

purge
