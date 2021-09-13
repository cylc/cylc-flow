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

# Cylc 7 stall backward compatibility, complex family case.

. "$(dirname "$0")/test_header"
set_test_number 13

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# It should now validate, with a deprecation message
TEST_NAME="${TEST_NAME_BASE}-validate_as_c7"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

DEPR_MSG_1=$(python -c \
  'from cylc.flow.workflow_files import SUITERC_DEPR_MSG; print(SUITERC_DEPR_MSG)')
grep_ok "${DEPR_MSG_1}" "${TEST_NAME}.stderr"

DEPR_MSG_2=$(python -c \
  'from cylc.flow.config import WorkflowConfig as cfg; print(cfg.CYLC7_GRAPH_COMPAT_MSG);')
grep_ok "${DEPR_MSG_2}" "${TEST_NAME}.stderr"

# Should stall and abort with unsatisfied "stall" tasks.
workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play -n --debug "${WORKFLOW_NAME}"

grep_workflow_log_ok grep-1 "Workflow stalled"
grep_workflow_log_ok grep-2 "WARNING - Unsatisfied prerequisites"
grep_workflow_log_ok grep-3 "stall01\.1 is waiting on"
grep_workflow_log_ok grep-4 "stall02\.1 is waiting on"
grep_workflow_log_ok grep-5 "stall03\.1 is waiting on"
grep_workflow_log_ok grep-6 "stall04\.1 is waiting on"
grep_workflow_log_ok grep-7 "stall05\.1 is waiting on"
grep_workflow_log_ok grep-8 "stall06\.1 is waiting on"
grep_workflow_log_ok grep-9 'Workflow shutting down \- "abort on stall timeout" is set'

purge
exit
