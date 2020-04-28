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

# Test that timed out event handlers get killed and recorded as failed.

. "$(dirname "$0")/test_header"

set_test_number 4

create_test_globalrc "
process pool timeout = PT10S" ""

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"

sed -e 's/^.* \([EW]\)/\1/' "${SUITE_RUN_DIR}/log/suite/log" >'log'

contains_ok 'log' <<__END__
ERROR - [(('event-handler-00', 'started'), 1) cmd] sleeper.sh foo.1
	[(('event-handler-00', 'started'), 1) ret_code] -9
	[(('event-handler-00', 'started'), 1) err] killed on timeout (PT10S)
WARNING - 1/foo/01 ('event-handler-00', 'started') failed
__END__

cylc suite-state "${SUITE_NAME}" >'suite-state.log'

contains_ok 'suite-state.log' << __END__
stopper, 1, succeeded
foo, 1, succeeded
__END__

purge_suite "${SUITE_NAME}"
exit
