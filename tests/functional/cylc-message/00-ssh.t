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
# Test "cylc message" in SSH mode, test needs to have compatible version
# installed on the remote host.
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
# TODO: Fix test once ssh task comms reinstated
skip_all 'ssh task comm not currently functional'

#-------------------------------------------------------------------------------
require_remote_platform
set_test_number 3

create_test_globalrc '' "
[platforms]
    [[${CYLC_TEST_PLATFORM}-ssh]]
        hosts = ${CYLC_TEST_HOST}
        communication method = ssh
"

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach --reference-test "${SUITE_NAME}"

run_fail "${TEST_NAME_BASE}-grep-DENIED-suite-log" \
    grep -q "\\[client-connect\\] DENIED .*@${CYLC_TEST_HOST}:cylc-message" \
    "$RUN_DIR/${SUITE_NAME}/log/suite/log"

purge_suite_platform "${CYLC_TEST_PLATFORM}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
