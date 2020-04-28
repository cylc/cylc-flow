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
# Test suite event handler, flexible interface
. "$(dirname "$0")/test_header"
set_test_number 4
OPT_SET=
if [[ "${TEST_NAME_BASE}" == *-globalcfg ]]; then
    create_test_globalrc "" "
[cylc]
    [[events]]
        handlers = echo 'Your %(suite)s suite has a %(event)s event and URL %(suite_url)s and suite-priority as %(suite-priority)s and suite-UUID as %(suite_uuid)s.'
        handler events = startup"
    OPT_SET='-s GLOBALCFG=True'
fi

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate ${OPT_SET} "${SUITE_NAME}"
# shellcheck disable=SC2086
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach ${OPT_SET} "${SUITE_NAME}"

LOGD="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/log"
SUITE_UUID="$(sqlite3 "${LOGD}/db" 'SELECT value FROM suite_params WHERE key=="uuid_str"')"
LOG_FILE="${LOGD}/suite/log"
grep_ok "\\[('suite-event-handler-00', 'startup') ret_code\\] 0" "${LOG_FILE}"
grep_ok "\\[('suite-event-handler-00', 'startup') out\\] Your ${SUITE_NAME} suite has a startup event and URL http://mysuites.com/${SUITE_NAME}.html and suite-priority as HIGH and suite-UUID as ${SUITE_UUID}." "${LOG_FILE}"

purge_suite "${SUITE_NAME}"
exit
