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
# Test "cylc stop --port=PORT" with no contact file
. "$(dirname "$0")/test_header"

set_test_number 5

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"
poll_grep_suite_log 'WARNING - suite stalled'
SRVD="${SUITE_RUN_DIR}/.service"
# Read host & port from contact file before removing it
HOST="$(awk -F= '$1 ~ /CYLC_SUITE_HOST/ {print $2}' "${SRVD}/contact")"
PORT="$(awk -F= '$1 ~ /CYLC_SUITE_PORT/ {print $2}' "${SRVD}/contact")"
if [[ -z "${PORT}" ]]; then
    exit 1
fi
rm -f "${SRVD}/contact"
run_fail "${TEST_NAME_BASE}-stop-1" cylc stop "${SUITE_NAME}"
contains_ok "${TEST_NAME_BASE}-stop-1.stderr" <<__ERR__
SuiteStopped: ${SUITE_NAME} is not running
__ERR__
run_ok "${TEST_NAME_BASE}-stop-2" \
    cylc stop --host="${HOST}" --port="${PORT}" "${SUITE_NAME}" \
    --max-polls='5' --interval='2'
purge_suite "${SUITE_NAME}"
exit
