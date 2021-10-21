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
#------------------------------------------------------------------------

# test the export of CYLC_WORKFLOW_ID and CYLC_WORKFLOW_ID

. "$(dirname "$0")/test_header"

set_test_number 4

cat > flow.cylc <<'__FLOW_CONFIG__'
[scheduler]
    cycle point format = %Y
    [[events]]
        stall timeout = PT0S

[scheduling]
    initial cycle point = 1066

    [[dependencies]]
        R1 = foo

[runtime]
    [[foo]]
        script = """
            echo "CYLC_WORKFLOW_ID is: ${CYLC_WORKFLOW_ID}"
            echo "CYLC_WORKFLOW_ID is: ${CYLC_WORKFLOW_ID}"
        """
__FLOW_CONFIG__

init_workflow "${TEST_NAME_BASE}" flow.cylc true

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-play" cylc play "${WORKFLOW_NAME}" --no-detach
named_grep_ok \
    "${TEST_NAME_BASE}-check-CYLC_WORKFLOW_ID" \
    "CYLC_WORKFLOW_ID is:.* ${WORKFLOW_NAME}" \
    "${WORKFLOW_RUN_DIR}/runN/log/job/1066/foo/NN/job.out"
named_grep_ok \
    "${TEST_NAME_BASE}-check-CYLC_WORKFLOW_ID" \
    "CYLC_WORKFLOW_ID is:.* ${WORKFLOW_NAME}/run1" \
    "${WORKFLOW_RUN_DIR}/runN/log/job/1066/foo/NN/job.out"

