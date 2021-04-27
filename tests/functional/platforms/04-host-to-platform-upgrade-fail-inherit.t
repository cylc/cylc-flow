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
# Parent and child tasks are both valid, before inheritance calculated.
# Child function not valid after inheritance.
# Check for task failure at job-submit.
. "$(dirname "$0")/test_header"
set_test_number 3

create_test_global_config '' "
# non-existent platform
[platforms]
    [[_wibble]]
"

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Both of these cases should validate ok.
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${WORKFLOW_NAME}"

# Run the workflow
workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

# Grep for inherit-fail to fail later at submit time
grep_ok "WorkflowConfigError:.*non-valid-child.1" \
    "${TEST_NAME_BASE}-run.stderr"

purge
exit
