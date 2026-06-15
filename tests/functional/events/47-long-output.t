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
# Test that a long output from an event handler is not going to hang or die.

. "$(dirname "$0")/test_header"

set_test_number 10

create_test_global_config "" "
[scheduler]
    process pool timeout = PT10S
"

# Long STDOUT output

init_workflow "${TEST_NAME_BASE}" <<__FLOW_CONFIG__
[scheduling]
    [[graph]]
        R1 = t1
[runtime]
    [[t1]]
        script = true
        [[[events]]]
            succeeded handlers = cat "${CYLC_REPO_DIR}/COPYING" "${CYLC_REPO_DIR}/COPYING" "${CYLC_REPO_DIR}/COPYING" && echo
__FLOW_CONFIG__
cd "$WORKFLOW_RUN_DIR" || exit 1
cat >'reference.log' <<'__REFLOG__'
Initial point: 1
Final point: 1
1/t1 -triggered off []
__REFLOG__
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach --reference-test "${WORKFLOW_NAME}"

cylc cat-log "${WORKFLOW_NAME}" >'catlog'
sed -n 's/^.*\(GNU GENERAL PUBLIC LICENSE\)/\1/p' 'catlog' >'log-1'
contains_ok 'log-1' <<'__LOG__'
GNU GENERAL PUBLIC LICENSE
GNU GENERAL PUBLIC LICENSE
GNU GENERAL PUBLIC LICENSE
__LOG__
run_ok "log-event-handler-00-out" \
    grep -qF "[(('event-handler-00', 'succeeded'), 1) out]" 'catlog'
run_ok "log-event-handler-ret-code" \
    grep -qF "[(('event-handler-00', 'succeeded'), 1) ret_code] 0" 'catlog'

purge

# REPEAT: Long STDERR output
init_workflow "${TEST_NAME_BASE}" <<__FLOW_CONFIG__
[scheduling]
    [[graph]]
        R1 = t1
[runtime]
    [[t1]]
        script = true
        [[[events]]]
            succeeded handlers = cat "${CYLC_REPO_DIR}/COPYING" "${CYLC_REPO_DIR}/COPYING" "${CYLC_REPO_DIR}/COPYING" >&2 && echo
__FLOW_CONFIG__
cd "${WORKFLOW_RUN_DIR}" || exit 1
cat >'reference.log' <<'__REFLOG__'
Initial point: 1
Final point: 1
1/t1 -triggered off []
__REFLOG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach --reference-test "${WORKFLOW_NAME}"

cylc cat-log "${WORKFLOW_NAME}" >'catlog'
sed -n 's/^.*\(GNU GENERAL PUBLIC LICENSE\)/\1/p' 'catlog' >'log-1'
contains_ok 'log-1' <<'__LOG__'
GNU GENERAL PUBLIC LICENSE
GNU GENERAL PUBLIC LICENSE
GNU GENERAL PUBLIC LICENSE
__LOG__
run_ok "log-event-handler-00-err" \
    grep -qF "[(('event-handler-00', 'succeeded'), 1) err]" 'catlog'
run_ok "log-event-handler-00-ret-code" \
    grep -qF "[(('event-handler-00', 'succeeded'), 1) ret_code] 0" 'catlog'

purge

exit
