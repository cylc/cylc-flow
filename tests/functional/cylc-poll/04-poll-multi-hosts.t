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
# Test poll multiple jobs on localhost and a remote host
export REQUIRE_PLATFORM='loc:remote comms:tcp'
. "$(dirname "$0")/test_header"
set_test_number 3

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}"

RUN_DIR="$RUN_DIR/${WORKFLOW_NAME}"
LOG="${RUN_DIR}/log/scheduler/log"
sed -n 's/^.*\(cylc jobs-poll\)/\1/p' "${LOG}" | sort -u >'edited-workflow-log'

sort >'edited-workflow-log-ref' <<__LOG__
cylc jobs-poll --debug -- '\$HOME/cylc-run/${WORKFLOW_NAME}/log/job' 1/remote-fail-1/01 1/remote-success-1/01 1/remote-success-2/01
cylc jobs-poll --debug -- '\$HOME/cylc-run/${WORKFLOW_NAME}/log/job' 1/local-fail-1/01 1/local-fail-2/01 1/local-success-1/01
__LOG__
cmp_ok 'edited-workflow-log' 'edited-workflow-log-ref'

purge
exit
