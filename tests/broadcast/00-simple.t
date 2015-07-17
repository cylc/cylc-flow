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
# Test broadcasts
. "$(dirname "$0")/test_header"
set_test_number 4
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --reference-test "${SUITE_NAME}"

DB_FILE="$(cylc get-global-config '--print-run-dir')/${SUITE_NAME}/cylc-suite.db"
NAME='select-broadcast-events.out'
sqlite3 "${DB_FILE}" \
    'SELECT change, point, namespace, key, value FROM broadcast_events
     ORDER BY time, change, point, namespace, key' >"${NAME}"
cmp_ok "${NAME}" <<'__SELECT__'
+|*|root|[environment]BCAST|ROOT
+|2010080800|foo|[environment]BCAST|FOO
+|*|bar|[environment]BCAST|BAR
+|2010080900|baz|[environment]BCAST|BAZ
+|2010080900|qux|[environment]BCAST|QUX
-|2010080900|qux|[environment]BCAST|QUX
+|*|wibble|[environment]BCAST|WIBBLE
-|*|wibble|[environment]BCAST|WIBBLE
+|*|ENS|[environment]BCAST|ENS
+|*|ENS1|[environment]BCAST|ENS1
+|2010080900|m2|[environment]BCAST|M2
+|*|m7|[environment]BCAST|M7
+|*|m8|[environment]BCAST|M8
+|*|m9|[environment]BCAST|M9
-|2010080800|foo|[environment]BCAST|FOO
__SELECT__

NAME='select-broadcast-states.out'
sqlite3 "${DB_FILE}" \
    'SELECT point, namespace, key, value FROM broadcast_states
     ORDER BY point, namespace, key' >"${NAME}"
cmp_ok "${NAME}" <<'__SELECT__'
*|ENS|[environment]BCAST|ENS
*|ENS1|[environment]BCAST|ENS1
*|bar|[environment]BCAST|BAR
*|m7|[environment]BCAST|M7
*|m8|[environment]BCAST|M8
*|m9|[environment]BCAST|M9
*|root|[environment]BCAST|ROOT
2010080900|baz|[environment]BCAST|BAZ
2010080900|m2|[environment]BCAST|M2
__SELECT__

purge_suite "${SUITE_NAME}"
exit
