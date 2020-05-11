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
# Test automatic custom template variables (with override) on restart.
. "$(dirname "$0")/test_header"

set_test_number 3

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}" \
    --set='FINAL_CYCLE_POINT=2020' --set='COMMAND=true'

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run "${SUITE_NAME}" \
    --set='FINAL_CYCLE_POINT=2020' --set='COMMAND=true' \
    --until=2018 --debug --no-detach

suite_run_ok "${TEST_NAME_BASE}-restart" \
    cylc restart "${SUITE_NAME}" --debug --no-detach --reference-test \
    --set='FINAL_CYCLE_POINT=2022'

purge_suite "${SUITE_NAME}"
exit
