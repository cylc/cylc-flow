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
# -----------------------------------------------------------------------------
# Test that invalid cycle point cli options for `cylc play` on
# run vs restart are ignored

. "$(dirname "$0")/test_header"

set_test_number 7

init_suite "${TEST_NAME_BASE}" <<'__FLOW__'
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
                cylc stop "$SUITE_NAME"
            fi
        """
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

# Cannot use 'ignore' on first start:
TEST_NAME="${TEST_NAME_BASE}-run"
run_ok "$TEST_NAME" cylc play "${SUITE_NAME}" --no-detach --fcp=ignore
log_scan "${TEST_NAME}-log-scan" "${SUITE_RUN_DIR}/log/suite/log" 20 2 \
    "WARNING - Ignoring option: --fcp=ignore" \
    "INFO - Final point: 3"

poll_suite_stopped

# Cannot use --icp or --startcp on restart:
TEST_NAME="${TEST_NAME_BASE}-restart"
run_ok "$TEST_NAME" cylc play "${SUITE_NAME}" --no-detach --icp=2
log_scan "${TEST_NAME}-log-scan" "${SUITE_RUN_DIR}/log/suite/log" 20 2 \
    "WARNING - Ignoring option: --icp=2" \
    "INFO - Initial point: 1"

poll_suite_stopped

purge
