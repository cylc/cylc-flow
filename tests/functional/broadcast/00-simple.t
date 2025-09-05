#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
# Test broadcasts
. "$(dirname "$0")/test_header"

set_test_number 5
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --no-detach --reference-test "${WORKFLOW_NAME}"
sort "${WORKFLOW_RUN_DIR}/share/broadcast.log" >'broadcast.log.sorted'
cmp_ok 'broadcast.ref' 'broadcast.log.sorted'

DB_FILE="${WORKFLOW_RUN_DIR}/log/db"
NAME='select-broadcast-events.out'
sqlite3 "${DB_FILE}" \
    'SELECT change, point, namespace, key, value FROM broadcast_events
     ORDER BY time, change, point, namespace, key' >"${NAME}"
cmp_ok "${NAME}" <<'__SELECT__'
+|*|root|[environment]BCAST|ROOT
+|20100808T00|foo|[environment]BCAST|FOO
+|*|bar|[environment]BCAST|BAR
+|20100809T00|baz|[environment]BCAST|BAZ
+|20100809T00|qux|[environment]BCAST|QUX
-|20100809T00|qux|[environment]BCAST|QUX
+|*|wibble|[environment]BCAST|WIBBLE
-|*|wibble|[environment]BCAST|WIBBLE
+|*|ENS|[environment]BCAST|ENS
+|*|ENS1|[environment]BCAST|ENS1
+|20100809T00|m2|[environment]BCAST|M2
+|*|m7|[environment]BCAST|M7
+|*|m8|[environment]BCAST|M8
+|*|m9|[environment]BCAST|M9
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
20100808T00|foo|[environment]BCAST|FOO
20100809T00|baz|[environment]BCAST|BAZ
20100809T00|m2|[environment]BCAST|M2
__SELECT__

purge
exit
