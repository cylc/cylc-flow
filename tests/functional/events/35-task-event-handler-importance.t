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
#------------------------------------------------------------------------------
# Test new runtime config item importance #2289
. "$(dirname "$0")/test_header"
#------------------------------------------------------------------------------
set_test_number 3 
#------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"
T1_ACTIVITY_LOG="${SUITE_RUN_DIR}/log/job/1/t1/NN/job-activity.log"

grep_ok \
    "\\[(('event-handler-00', 'failed'), 1) out\\] NAME = t1 POINT = 1 IMPORTANCE = 3 COLOR = red SUITE-PRIORITY = HIGH" \
    "${T1_ACTIVITY_LOG}"    
#------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
