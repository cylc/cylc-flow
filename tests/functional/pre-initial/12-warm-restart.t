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
# Test warm start persists across restarts
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 6
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" warm-start
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-run-paused
workflow_run_ok "${TEST_NAME}" cylc play "${WORKFLOW_NAME}" --startcp=20130101T12 --pause
#-------------------------------------------------------------------------------
cylc stop --max-polls=10 --interval=2 "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-restart
workflow_run_ok "${TEST_NAME}" cylc play "${WORKFLOW_NAME}"
# Ensure workflow has started
poll_workflow_running
#-------------------------------------------------------------------------------
# Check pre-reqs
TEST_NAME=${TEST_NAME_BASE}-check-prereq
run_ok "${TEST_NAME}" cylc show "${WORKFLOW_NAME}//20130101T1200Z/foo" --list-prereqs
cmp_ok "${TEST_NAME}.stdout" <<'__OUT__'
20130101T0600Z/foo succeeded
__OUT__
#-------------------------------------------------------------------------------
# Stop workflow
cylc stop --max-polls=10 --interval=2 "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
DB_FILE="${RUN_DIR}/${WORKFLOW_NAME}/log/db"
NAME='database-entry'
sqlite3 "${DB_FILE}" \
    "SELECT value FROM workflow_params WHERE key=='startcp'" >"${NAME}"
cmp_ok "${NAME}" <<<'20130101T12'
#-------------------------------------------------------------------------------
purge
