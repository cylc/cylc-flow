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

# Test clock xtriggers
. "$(dirname "$0")/test_header"

# shellcheck disable=SC2317
run_workflow() {
  cylc play --no-detach --debug "$1" \
    -s "START='$2'" -s "HOUR='$3'" -s "OFFSET='$4'"
}

set_test_number 5
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

NOW="$(date -u '+%Y%m%dT%H')"

# Initial cycle point is the hour just passed.
START="$NOW"
HOUR="$(date -u +%H)"
OFFSET="PT0S"

# Validate and run with "now" clock trigger (satisfied).
run_ok "${TEST_NAME_BASE}-val" cylc validate "${WORKFLOW_NAME}" \
   -s "START='${START}'" -s "HOUR='${HOUR}'" -s "OFFSET='${OFFSET}'"

TEST_NAME="${TEST_NAME_BASE}-now"
run_ok "${TEST_NAME}" run_workflow "${WORKFLOW_NAME}" "${START}" "${HOUR}" "${OFFSET}"

# Run with "past" clock trigger (satisfied).
START="$(cylc cycle-point "${NOW}" --offset-hour='-10')"
HOUR="$(cylc cycle-point "${START}" --print-hour)"
OFFSET='PT0S'

delete_db
TEST_NAME="${TEST_NAME_BASE}-past"
run_ok "${TEST_NAME}" run_workflow "${WORKFLOW_NAME}" "${START}" "${HOUR}" "${OFFSET}"

# Run with "future" clock trigger (not satisfied - stall and abort).
START="$(cylc cycle-point "${NOW}" --offset-hour=10)"
HOUR="$(cylc cycle-point "${START}" --print-hour)"

delete_db
TEST_NAME="${TEST_NAME_BASE}-future"
run_fail "${TEST_NAME}" run_workflow "${WORKFLOW_NAME}" "${START}" "${HOUR}" "${OFFSET}"
LOG="$(cylc cat-log -m p "${WORKFLOW_NAME}")"
grep_ok "inactivity timer timed out" "${LOG}"

purge
exit
