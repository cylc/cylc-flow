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
# Test clock triggering is working, with no offset argument
# https://github.com/cylc/cylc-flow/issues/1417
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}" -s START="$(date '+%Y%m%dT%H%z')" \
    -s HOUR="$(date '+%H')" -s 'UTC_MODE=False' -s 'TIMEOUT=PT0.2M'
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-run-now" \
    cylc run --debug --no-detach "${SUITE_NAME}" \
    -s START="$(date '+%Y%m%dT%H%z')" \
    -s HOUR="$(date '+%H')" -s 'UTC_MODE=False' -s 'TIMEOUT=PT0.2M'
#-------------------------------------------------------------------------------
NOW="$(date '+%Y%m%dT%H')"
START="$(cylc cycle-point "${NOW}" --offset-hour='-10')$(date '+%z')"
HOUR="$(cylc cycle-point "${NOW}" --offset-hour='-10' --print-hour)"
run_ok "${TEST_NAME_BASE}-run-past" \
    cylc run --debug --no-detach "${SUITE_NAME}" -s START="${START}" \
    -s HOUR="${HOUR}" -s 'UTC_MODE=False' -s 'TIMEOUT=PT1M'
#-------------------------------------------------------------------------------
NOW="$(date '+%Y%m%dT%H')"
START="$(cylc cycle-point "${NOW}" --offset-hour='10')$(date '+%z')"
HOUR="$(cylc cycle-point "${NOW}" --offset-hour='10' --print-hour)"
run_fail "${TEST_NAME_BASE}-run-later" \
    cylc run --debug --no-detach "${SUITE_NAME}" -s START="${START}" \
    -s HOUR="${HOUR}" -s 'UTC_MODE=False' -s 'TIMEOUT=PT0.2M'
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
