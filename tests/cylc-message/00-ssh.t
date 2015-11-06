#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
CYLC_TEST_HOST="$( \
    cylc get-global-config -i '[test battery]remote host' 2>'/dev/null')"
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip_all '"[test battery]remote host": not defined'
fi
set_test_number 3

mkdir 'conf'
cat >>'conf/global.rc' <<__GLOBAL_RC__
[hosts]
    [[${CYLC_TEST_HOST}]]
        task communication method = ssh
__GLOBAL_RC__
export CYLC_CONF_PATH="${PWD}/conf"

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
# Note: Don't install passphrase on remote host. Message should only return via
# SSH.

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}" -s "CYLC_TEST_HOST=${CYLC_TEST_HOST}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --reference-test "${SUITE_NAME}" \
    -s "CYLC_TEST_HOST=${CYLC_TEST_HOST}"

run_fail "${TEST_NAME_BASE}-grep-DENIED-suite-log" \
    grep -q "\\[client-connect\\] DENIED .*@${CYLC_TEST_HOST}:cylc-message" \
    "$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/log/suite/log"

ssh -oBatchMode=yes -oConnectTimeout=5 "${CYLC_TEST_HOST}" \
    "rm -rf '.cylc/${SUITE_NAME}' 'cylc-run/${SUITE_NAME}'"
purge_suite "${SUITE_NAME}"
exit
