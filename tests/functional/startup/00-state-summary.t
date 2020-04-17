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
#-------------------------------------------------------------------------------
# Test that the state summary updates immediately on start-up.
# See https://github.com/cylc/cylc-flow/pull/1756
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
# Suite runs and shuts down with a failed task.
cylc run --no-detach "${SUITE_NAME}" > /dev/null 2>&1
# Restart with a failed task and a succeeded task.
cylc restart "${SUITE_NAME}"
poll_grep_suite_log -F '[foo.1] status=failed: (polled)failed'
cylc dump "${SUITE_NAME}" > dump.out
TEST_NAME=${TEST_NAME_BASE}-grep
# State summary should not just say "Initializing..."
grep_ok "state totals={'failed': 1}" dump.out
#-------------------------------------------------------------------------------
cylc stop --max-polls=10 --interval=2 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
