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
set_test_number 5

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

purge_suite "${SUITE_NAME}"
exit
