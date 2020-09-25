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

# Test clock xtriggers
. "$(dirname "$0")/test_header"

run_suite() {
  cylc run --no-detach --debug "$1" -s "START=$2" -s "HOUR=$3" -s "OFFSET=$4"
}

set_test_number 5
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

NOW="$(date '+%Y%m%dT%H')"

# Validate and run with "now" clock trigger (satisfied).
START="$NOW"
HOUR="$(date +%H)"
OFFSET="PT0S"

run_ok "${TEST_NAME_BASE}-val" cylc validate "${SUITE_NAME}" \
   -s "START=${START}" -s "HOUR=${HOUR}" -s "OFFSET=${OFFSET}"

TEST_NAME="${TEST_NAME_BASE}-now"
run_ok "${TEST_NAME}" run_suite "${SUITE_NAME}" "${START}" "${HOUR}" "${OFFSET}"

# Run with "past" clock trigger (satisfied).
START="$(cylc cycle-point "${NOW}" --offset-hour='-10')"
HOUR="$(cylc cycle-point "${START}" --print-hour)"
OFFSET='PT0S'

TEST_NAME="${TEST_NAME_BASE}-past"
run_ok "${TEST_NAME}" run_suite "${SUITE_NAME}" "${START}" "${HOUR}" "${OFFSET}"

# Run with "future" clock trigger (not satisfied - stall and abort).
START="$(cylc cycle-point "${NOW}" --offset-hour=10)"
HOUR="$(cylc cycle-point "${START}" --print-hour)"

TEST_NAME="${TEST_NAME_BASE}-future"
run_fail "${TEST_NAME}" run_suite "${SUITE_NAME}" "${START}" "${HOUR}" "${OFFSET}"
LOG="$(cylc cat-log -m p "${SUITE_NAME}")"
grep_ok "suite timed out after inactivity" "${LOG}"

purge_suite "${SUITE_NAME}"
exit
