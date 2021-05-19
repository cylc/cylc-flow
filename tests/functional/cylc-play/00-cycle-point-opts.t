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
# -----------------------------------------------------------------------------
# Test that invalid cycle point CLI options for `cylc play` on
# start vs restart cause the scheduler to abort.

. "$(dirname "$0")/test_header"

set_test_number 10

init_workflow "${TEST_NAME_BASE}" <<'__FLOW__'
[scheduling]
    cycling mode = integer
    runahead limit = P2
    initial cycle point = 1
    final cycle point = 3
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = """
            if [[ "$CYLC_TASK_CYCLE_POINT" == 2 ]]; then
                cylc stop "$CYLC_WORKFLOW_NAME"
            fi
        """
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

WFLOG="${WORKFLOW_RUN_DIR}/log/workflow/log"

# Cannot use 'ignore' on first run:

TEST_NAME="${TEST_NAME_BASE}-run-abort"
workflow_run_fail "$TEST_NAME" cylc play "${WORKFLOW_NAME}" --no-detach --fcp=ignore
grep_ok "option \-\-fcp=ignore is only valid for restart." "${WFLOG}"

# Do first run:

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "$TEST_NAME" cylc play "${WORKFLOW_NAME}" --stopcp=1 --no-detach

# Cannot use --icp or --startcp or --start-task on restart:

TEST_NAME="${TEST_NAME_BASE}-restart-abort-icp"
workflow_run_fail "$TEST_NAME" cylc play "${WORKFLOW_NAME}" --no-detach --icp=2
grep_ok "option \-\-icp is not valid for restart." "${WFLOG}"

TEST_NAME="${TEST_NAME_BASE}-restart-abort-startcp"
workflow_run_fail "$TEST_NAME" cylc play "${WORKFLOW_NAME}" --no-detach --startcp=2
grep_ok "option \-\-startcp is not valid for restart." "${WFLOG}"

TEST_NAME="${TEST_NAME_BASE}-restart-abort-starttask"
workflow_run_fail "$TEST_NAME" cylc play "${WORKFLOW_NAME}" --no-detach --start-task=foo.2
grep_ok "option \-\-starttask is not valid for restart." "${WFLOG}"

purge
