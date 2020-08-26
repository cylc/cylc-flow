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
# Test late event handler with restart. Event should be emitted once.
. "$(dirname "$0")/test_header"
set_test_number 4
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run --debug --no-detach "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-restart" \
    cylc restart --debug --no-detach "${SUITE_NAME}"
# Check that the suite has emitted a single late event.
grep -c 'WARNING.*late (late-time=.*)' \
    <(cat "${SUITE_RUN_DIR}/log/suite/log."*) \
    >'grep-log.out'
cmp_ok 'grep-log.out' <<<'1'
grep -c 'late (late-time=.*)' \
    "${SUITE_RUN_DIR}/log/suite/my-handler.out" \
    > 'grep-my-handler.out'
cmp_ok 'grep-my-handler.out' <<<'1'

# Suspend the suite, simulate Ctrl-Z
kill -SIGSTOP "${SUITE_PID}"
# (kill does not return until signal is handled; otherwise "cat /proc/PID/stat"
#  should start with "PID (cylc-run) T")

# don't let any other errors effect our test
cylc scan -n "${SUITE_NAME}" \
    >"${TEST_NAME_BASE}-scan.stdout" \
    2>"${TEST_NAME_BASE}-scan.stderr"

# Check for timeout error.
grep_ok "TIMEOUT" "${TEST_NAME_BASE}-scan.stdout"
grep_ok "Timeout waiting for server response. This could be due to network or server issues. Check the suite log." "${TEST_NAME_BASE}-scan.stderr"
# Tell the suite to continue
kill -SIGCONT "${SUITE_PID}"
# (kill does not return until signal is handled)
cylc stop --max-polls=5 --interval=2 "${SUITE_NAME}"
purge
exit
