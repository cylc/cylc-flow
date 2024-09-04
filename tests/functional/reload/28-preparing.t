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

# Test for duplicate job submissions when preparing tasks get flushed
# prior to reload - see https://github.com/cylc/cylc-flow/pull/6345

. "$(dirname "$0")/test_header"
set_test_number 4

# Strap the process pool size down to 1, so that the first task is stuck
# in the preparing state until the startup event handler finishes.

create_test_global_config "" "
[scheduler]
    process pool size = 1
"

# install and play the workflow, then reload it and wait for it to finish.
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-vip" cylc validate "${WORKFLOW_NAME}"
run_ok "${TEST_NAME_BASE}-reload" cylc play "${WORKFLOW_NAME}"
run_ok "${TEST_NAME_BASE}-reload" cylc reload "${WORKFLOW_NAME}"
poll_grep_workflow_log -F 'INFO - DONE'

# check that task `foo` was only submitted once.
count_ok "1/foo.*submitted to" "${WORKFLOW_RUN_DIR}/log/scheduler/log" 1

purge
