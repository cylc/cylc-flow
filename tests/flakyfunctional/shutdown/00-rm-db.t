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
# Test that removing the DB quickly after a shutdown does not cause it to be
# regenerated due to any outstanding connection to the DB.
# NOTE: this test is not guaranteed to catch the issue, but is more likely
# to do so on slower filesystems. However, faster filesystems are
# less likely to have the original issue in the first place. See
# https://github.com/cylc/cylc-flow/pull/4046

. "$(dirname "$0")/test_header"

set_test_number 5

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[dependencies]]
        R1 = foo
__FLOW_CONFIG__

pri_db="${WORKFLOW_RUN_DIR}/.service/db"
pub_db="${WORKFLOW_RUN_DIR}/log/db"

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play "${WORKFLOW_NAME}"

poll_workflow_running
poll_workflow_stopped  # This waits for contact file to be removed
# Delete the DB without delay
rm -f "$pri_db" "$pub_db"
# Check if DB exists without delay
exists_fail "$pri_db"
exists_fail "$pub_db"

sleep 10
# Check if DB exists after delay
exists_fail "$pri_db"
exists_fail "$pub_db"

purge
exit
