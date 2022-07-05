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
# Test intercycle dependencies.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 6
#-------------------------------------------------------------------------------
# test initial and final cycle point special notation (^, $)
TEST_NAME=${TEST_NAME_BASE}
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
TEST_NAME="${TEST_NAME_BASE}-run"
run_ok "${TEST_NAME}" cylc play "${WORKFLOW_NAME}" --debug --no-detach

TEST_NAME=${TEST_NAME_BASE}-out
grep_ok "20160101T0000Z/foo" "$HOME/cylc-run/${WORKFLOW_NAME}/log/scheduler/log"
grep_ok "20160101T0000Z/bar" "$HOME/cylc-run/${WORKFLOW_NAME}/log/scheduler/log"
grep_ok "20160101T0100Z/baz" "$HOME/cylc-run/${WORKFLOW_NAME}/log/scheduler/log"
grep_ok "20160101T2300Z/boo" "$HOME/cylc-run/${WORKFLOW_NAME}/log/scheduler/log"
grep_ok "20160102T0000Z/bot" "$HOME/cylc-run/${WORKFLOW_NAME}/log/scheduler/log"
#-------------------------------------------------------------------------------
purge
