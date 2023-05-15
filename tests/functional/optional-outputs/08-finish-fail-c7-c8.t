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

#-------------------------------------------------------------------------
# Test handling of failed tasks in finish triggers (non back-compat mode).
# See comments in finish-fail-c7/suite.rc

. "$(dirname "$0")/test_header"
set_test_number 3

# (Note install will issue a back-compat mode message here).
install_workflow "${TEST_NAME_BASE}" finish-fail-c7

# Turn of back-compat mode:
mv "${WORKFLOW_RUN_DIR}/suite.rc" "${WORKFLOW_RUN_DIR}/flow.cylc"

# Validate with a deprecation message
TEST_NAME="${TEST_NAME_BASE}-validate_as_c8"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

DEPR_MSG="deprecated graph items were automatically upgraded"  # (not back-compat)
grep_ok "${DEPR_MSG}" "${TEST_NAME}.stderr"

# No stall expected.
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach --debug "${WORKFLOW_NAME}"

purge
