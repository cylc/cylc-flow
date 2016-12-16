#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
# Test restart from a checkpoint before a reload
. "$(dirname "$0")/test_header"

set_test_number 4

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
cp -p 'suite.rc' 'suite1.rc'

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

# Suite reloads+inserts new task to mess up prerequisites - suite should stall
suite_run_fail "${TEST_NAME_BASE}-run" \
    timeout 120 cylc run "${SUITE_NAME}" --debug
# Restart should stall in exactly the same way
suite_run_fail "${TEST_NAME_BASE}-restart-1" \
    timeout 60 cylc restart "${SUITE_NAME}" --debug

# Restart from a checkpoint before the reload should allow the suite to proceed
# normally.
cp -p 'suite1.rc' 'suite.rc'
suite_run_ok "${TEST_NAME_BASE}-restart-2" \
    timeout 120 cylc restart "${SUITE_NAME}" \
    --checkpoint=1 --debug --reference-test

purge_suite "${SUITE_NAME}"
exit
