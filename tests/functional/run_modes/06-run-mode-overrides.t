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

# Test that broadcasting a change in [runtime][<namespace>]run mode
# Leads to the next submission from that task to be in the updated
# mode.

. "$(dirname "$0")/test_header"
set_test_number 15

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play "${WORKFLOW_NAME}" \
        --no-detach

JOB_LOGS="${WORKFLOW_RUN_DIR}/log/job/1000"

# Ghost modes do not leave log folders:
for MODE in simulation skip; do
    run_fail "${TEST_NAME_BASE}-no-${MODE}-task-folder" ls "${JOB_LOGS}/${MODE}_"
done

# Live modes leave log folders:
for MODE in default live dummy; do
    run_ok "${TEST_NAME_BASE}-${MODE}-task-folder" ls "${JOB_LOGS}/${MODE}_"
done

# Default defaults to live, and live is live:
for MODE in default live; do
    named_grep_ok "${TEST_NAME_BASE}-default-task-live" "===.*===" "${JOB_LOGS}/${MODE}_/NN/job.out"
done

# Dummy produces a job.out, containing dummy message:
named_grep_ok "${TEST_NAME_BASE}-default-task-live" "dummy job succeed" "${JOB_LOGS}/dummy_/NN/job.out"

purge

# Do it again with a workflow in simulation.
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play "${WORKFLOW_NAME}" \
        --no-detach \
        --mode simulation

JOB_LOGS="${WORKFLOW_RUN_DIR}/log/job/1000"

# Live modes leave log folders:
for MODE in live dummy; do
    run_ok "${TEST_NAME_BASE}-${MODE}-task-folder" ls "${JOB_LOGS}/${MODE}_"
done

# Ghost modes do not leave log folders:
run_fail "${TEST_NAME_BASE}-no-default-task-folder" ls "${JOB_LOGS}/default_"

purge
exit 0
