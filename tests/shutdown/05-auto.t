#!/bin/bash
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
# Test auto shutdown after all tasks have finished.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 6
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
# Test that normal auto-shutdown works.
TEST_NAME=${TEST_NAME_BASE}-auto-stop
suite_run_ok "${TEST_NAME}" cylc run --debug --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
# Test that auto-shutdown can be disabled (CLI)
TEST_NAME=${TEST_NAME_BASE}-no-autostop-ping
cylc run --no-auto-shutdown "${SUITE_NAME}"
sleep 15
run_ok "${TEST_NAME}" cylc ping "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-stop
run_ok "${TEST_NAME}" cylc stop --max-polls=10 --interval=2 "${SUITE_NAME}"
#-------------------------------------------------------------------------------
# Test that auto-shutdown can be disabled (suite.rc)
export SUITE_DISABLE_AUTO_SHUTDOWN=true
TEST_NAME=${TEST_NAME_BASE}-no-autostop-ping-2
cylc run "${SUITE_NAME}"
sleep 15
run_ok "${TEST_NAME}" cylc ping "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-stop-2
run_ok "${TEST_NAME}" cylc stop --max-polls=10 --interval=2 "${SUITE_NAME}"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
