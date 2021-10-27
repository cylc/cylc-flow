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
# Test clock triggering is working
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}" \
    -s "START='$(date '+%Y%m%dT%H%z')'" \
    -s "HOUR='$(date '+%H')'" \
    -s "CPTZ='$(date '+%z')'" \
    -s 'OFFSET="PT0S"' \
    -s 'TIMEOUT="PT12S"'
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-run-now" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}" \
    -s "START='$(date '+%Y%m%dT%H%z')'" \
    -s "HOUR='$(date '+%H')'" \
    -s "CPTZ='$(date '+%z')'" \
    -s 'OFFSET="PT0S"' \
    -s 'TIMEOUT="PT12S"'
#-------------------------------------------------------------------------------
delete_db
TZSTR="$(date '+%z')"
NOW="$(date '+%Y%m%dT%H')"
run_ok "${TEST_NAME_BASE}-run-past" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}" \
    -s "START='$(cylc cycle-point "${NOW}" --offset-hour='-10')${TZSTR}'" \
    -s "HOUR='$(cylc cycle-point "${NOW}" --offset-hour='-10' --print-hour)'" \
    -s "CPTZ='$(date '+%z')'" \
    -s 'OFFSET="PT0S"' \
    -s 'TIMEOUT="PT1M"'
#-------------------------------------------------------------------------------
delete_db
NOW="$(date '+%Y%m%dT%H')"
run_fail "${TEST_NAME_BASE}-run-later" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}" \
    -s "START='$(cylc cycle-point "${NOW}" --offset-hour='10')${TZSTR}'" \
    -s "HOUR='$(cylc cycle-point "${NOW}" --offset-hour='10' --print-hour)'" \
    -s "CPTZ='$(date '+%z')'" \
    -s 'OFFSET="PT0S"' \
    -s 'TIMEOUT="PT12S"'
#-------------------------------------------------------------------------------
purge
exit
