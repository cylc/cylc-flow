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

# Testing Skip mode functionality.

. "$(dirname "$0")/test_header"
set_test_number 11

# Install and run the workflow in live mode (default).
# Check that tasks with run mode unset and run mode = live
# leave log files, and that skip mode tasks don't.
TEST_NAME="${TEST_NAME_BASE}:live-workflow"
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME}:validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME}:play" \
    cylc play "${WORKFLOW_NAME}" \
        --no-detach

JOB_LOGS="${WORKFLOW_RUN_DIR}/log/job/1000"
run_fail "${TEST_NAME}:config run mode=skip" ls "${JOB_LOGS}/skip_"
for MODE in default live; do
    named_grep_ok "${TEST_NAME}:config run mode=${MODE}" "===.*===" "${JOB_LOGS}/${MODE}_/NN/job.out"
done

# After broadcasting a change in run_mode to task default_ it now runs
# in skip mode and fails to produce a log file:
JOB_LOGS="${WORKFLOW_RUN_DIR}/log/job/1001"
run_fail "${TEST_NAME}:broadcast run mode=skip" ls "${JOB_LOGS}/default_/"

purge

# Install and run the workflow in skip mode.
# Check that tasks with run mode unset and run mode = skip
# don't leave log files, and that skip mode tasks does.
TEST_NAME="${TEST_NAME_BASE}:skip-workflow"
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
workflow_run_ok "${TEST_NAME}:run" \
    cylc play "${WORKFLOW_NAME}" \
        --no-detach \
        --mode skip \
        --set='changemode="live"' \
        --final-cycle-point=1000

JOB_LOGS="${WORKFLOW_RUN_DIR}/log/job/1000"
run_ok "${TEST_NAME}:run mode=live" ls "${JOB_LOGS}/live_"
run_fail "${TEST_NAME}:run mode=default" ls "${JOB_LOGS}/default_"
run_fail "${TEST_NAME}:run mode=skip" ls "${JOB_LOGS}/skip_"
JOB_LOGS="${WORKFLOW_RUN_DIR}/log/job/1000"
named_grep_ok "${TEST_NAME}:run mode=live" "===.*===" "${JOB_LOGS}/live_/NN/job.out"

purge
exit 0
