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
# Test "cylc get-suite-contact" basic usage.
. "$(dirname "$0")/test_header"
set_test_number 6
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[cylc]
    cycle point format = %Y
[scheduling]
    initial cycle point = 2016
    [[graph]]
        R1 = t1
[runtime]
    [[t1]]
        script = true
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_fail "${TEST_NAME_BASE}-get-suite-contact-1" \
    cylc get-suite-contact "${SUITE_NAME}"
cmp_ok "${TEST_NAME_BASE}-get-suite-contact-1.stderr" <<__ERR__
CylcError: ${SUITE_NAME}: cannot get contact info, suite not running?
__ERR__
run_ok "${TEST_NAME_BASE}-run-hold" cylc run --hold "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-get-suite-contact-2" \
    cylc get-suite-contact "${SUITE_NAME}"
contains_ok "${TEST_NAME_BASE}-get-suite-contact-2.stdout" \
    "${SUITE_RUN_DIR}/.service/contact"

cylc stop --max-polls=60 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
