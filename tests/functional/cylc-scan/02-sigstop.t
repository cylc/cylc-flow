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
# Test "cylc scan" on suite suspended with SIGSTOP
. "$(dirname "$0")/test_header"
set_test_number 5
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run --hold "${SUITE_NAME}"
sleep 5
SUITE_PID=$(cylc get-suite-contact "${SUITE_NAME}" | \
  awk '/CYLC_SUITE_PROCESS/ {print $1}' | sed -e 's/^.*=//')

# Suspend the suite, simulate Ctrl-Z
sleep 1
kill -SIGSTOP "${SUITE_PID}"
sleep 1
run_ok "${TEST_NAME_BASE}-scan" cylc scan
# ensure there is no traceback
grep_ok "TIMEOUT" "${TEST_NAME_BASE}-scan.stdout"
grep_ok "Timeout waiting for server response" "${TEST_NAME_BASE}-scan.stderr"
# Tell the suite to continue
kill -SIGCONT "${SUITE_PID}"
sleep 1
cylc stop --max-polls=5 --interval=2 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
