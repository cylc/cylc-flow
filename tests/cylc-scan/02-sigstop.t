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
# Test "cylc scan" on suite suspended with SIGSTOP
. "$(dirname "$0")/test_header"
set_test_number 4
create_test_globalrc
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run --hold "${SUITE_NAME}"
SUITE_PID=$(awk '/\+ PID: / {print $3}' "${TEST_NAME_BASE}-run.stdout")
SUITE_PORT=$(awk '/\+ Port: / {print $3}' "${TEST_NAME_BASE}-run.stdout")
# Suspend the suite, simulate Ctrl-Z
sleep 1
kill -SIGSTOP "${SUITE_PID}"
sleep 1
run_ok "${TEST_NAME_BASE}-scan" cylc scan 'localhost'
contains_ok "${TEST_NAME_BASE}-scan.stderr" <<__ERR__
WARNING, scan timed out, no result for the following:
  localhost:${SUITE_PORT}
__ERR__
# Tell the suite to continue
kill -SIGCONT "${SUITE_PID}"
sleep 1
cylc stop --max-polls=5 --interval=2 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
