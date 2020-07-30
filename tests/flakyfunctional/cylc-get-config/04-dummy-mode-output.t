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
# Test for completion of custom outputs in dummy and sim modes.
# And no duplication dummy outputs (GitHub #2064)
. "$(dirname "$0")/test_header"

set_test_number 10

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate --debug "${SUITE_NAME}"

# Live mode run: outputs not received, suite shuts down early without running baz
suite_run_ok "${TEST_NAME_BASE}-run-live" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
LOG="$(cylc log -m p "$SUITE_NAME")"
count_ok '(received)meet' "${LOG}" 0
count_ok '(received)greet' "${LOG}" 0

# Dummy and sim mode: outputs auto-completed, baz runs
suite_run_ok "${TEST_NAME_BASE}-run-dummy" \
    cylc run -m 'dummy' --reference-test --debug --no-detach "${SUITE_NAME}"
LOG="$(cylc log -m p "$SUITE_NAME")"
count_ok '(received)meet' "${LOG}" 1
count_ok '(received)greet' "${LOG}" 1

suite_run_ok "${TEST_NAME_BASE}-run-simulation" \
    cylc run -m 'simulation' --reference-test --debug --no-detach "${SUITE_NAME}"
LOG="$(cylc log -m p "$SUITE_NAME")"
count_ok '(received)meet' "${LOG}" 1
count_ok '(received)greet' "${LOG}" 1

purge_suite "${SUITE_NAME}"
exit
