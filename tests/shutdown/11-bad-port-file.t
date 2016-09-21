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
# Test "cylc stop --port=PORT" with a corrupted port file
. "$(dirname "$0")/test_header"

set_test_number 5

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"
LOGD="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/log"
poll "! grep -q 'WARNING - suite stalled' '${LOGD}/suite/log'"
PORTSD="$(cylc get-global-config --item='[communication]ports directory')"
while [[ "${PORTSD}" == */ ]]; do  # remove trailing slashes
    PORTSD="${PORTSD%/}"
done
if [[ -z "${PORTSD}" ]]; then
    exit 1
fi
# Read port from port file before corrupting it
PORT="$(head -1 "${PORTSD}/${SUITE_NAME}")"
if [[ -z "${PORT}" ]]; then
    exit 1
fi
echo 'garbage' >"${PORTSD}/${SUITE_NAME}"
run_fail "${TEST_NAME_BASE}-stop-1" cylc stop "${SUITE_NAME}"
contains_ok "${TEST_NAME_BASE}-stop-1.stderr" <<__ERR__
'ERROR, bad content in port file: ${PORTSD}/${SUITE_NAME}'
__ERR__
run_ok "${TEST_NAME_BASE}-stop-2" \
    cylc stop --port="${PORT}" "${SUITE_NAME}" --max-polls='5' --interval='2'
purge_suite "${SUITE_NAME}"
exit
