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

# "cylc set" proposal examples: 2 - Set off-flow outputs to prevent a new flow from stalling.
# https://cylc.github.io/cylc-admin/proposal-cylc-set.html#2-set-off-flow-prerequisites-to-prep-for-a-new-flow

. "$(dirname "$0")/test_header"
set_test_number 11

install_and_validate
reftest_run

# Check that we set:
#  - all the required outputs of a_cold
#  - the requested and implied outputs of b_cold and c_cold

grep_workflow_log_ok "${TEST_NAME_BASE}-grep-a1" '1/a_cold.* setting missed output: submitted'
grep_workflow_log_ok "${TEST_NAME_BASE}-grep-a2" '1/a_cold.* setting missed output: started'
grep_workflow_log_ok "${TEST_NAME_BASE}-grep-a3" 'output 1/a_cold:succeeded completed'

grep_workflow_log_ok "${TEST_NAME_BASE}-grep-a1" '1/b_cold.* setting missed output: submitted'
grep_workflow_log_ok "${TEST_NAME_BASE}-grep-a2" '1/b_cold.* setting missed output: started'
grep_workflow_log_ok "${TEST_NAME_BASE}-grep-b3" 'output 1/b_cold:succeeded completed'

grep_workflow_log_ok "${TEST_NAME_BASE}-grep-a1" '1/c_cold.* setting missed output: submitted'
grep_workflow_log_ok "${TEST_NAME_BASE}-grep-a2" '1/c_cold.* setting missed output: started'
grep_workflow_log_ok "${TEST_NAME_BASE}-grep-c3" 'output 1/c_cold:succeeded completed'

purge
