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
# Test reloading global configuration
. "$(dirname "$0")/test_header"
set_test_number 6

create_test_global_config "" ""

TEST_NAME="${TEST_NAME_BASE}"
install_workflow "${TEST_NAME}" "${TEST_NAME_BASE}"

# Validate the config
run_ok "${TEST_NAME}-validate" cylc validate "${WORKFLOW_NAME}"

# Run the workflow
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --no-detach -v

# Reload happened
grep_ok "Reloading the global configuration" "${WORKFLOW_RUN_DIR}/log/scheduler/01-start-01.log"

# But there was an error in the workflow config, so the change rolled back
grep_ok "Reload failed - IllegalItemError: garbage" "${WORKFLOW_RUN_DIR}/log/scheduler/log"

# Reload has rolled back in all tasks
grep_fail "global init-script reloaded!" "${WORKFLOW_RUN_DIR}/log/job/1/b/01/job.out"
grep_fail "global init-script reloaded!" "${WORKFLOW_RUN_DIR}/log/job/1/c/01/job.out"

purge
exit
