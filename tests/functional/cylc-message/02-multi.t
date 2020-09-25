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
# Test "cylc message" with multiple messages.

. "$(dirname "$0")/test_header"

set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run --debug --no-detach "${SUITE_NAME}"

LOG="${SUITE_RUN_DIR}/log/suite/log"
sed -n -e 's/^.* \([A-Z]* - \[foo.1\] status=running: (received).*$\)/\1/p' \
       -e '/\tbadness\|\tslowness\|\tand other incorrectness/p' \
    "${LOG}" >'sed.out'
sed -i 's/\(^.*\) at .*$/\1/;' 'sed.out'

# Note: the continuation bit gets printed twice, because the message gets a
# warning as being unhandled.
cmp_ok 'sed.out' <<'__LOG__'
WARNING - [foo.1] status=running: (received)Warn this
INFO - [foo.1] status=running: (received)Greeting
WARNING - [foo.1] status=running: (received)Warn that
DEBUG - [foo.1] status=running: (received)Remove stuffs such as
	badness
	slowness
	and other incorrectness.
	badness
	slowness
	and other incorrectness.
INFO - [foo.1] status=running: (received)whatever
INFO - [foo.1] status=running: (received)succeeded
__LOG__

purge_suite "${SUITE_NAME}"
exit
