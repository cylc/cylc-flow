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
# Test workflow event handler, flexible interface
. "$(dirname "$0")/test_header"
set_test_number 4
OPT_SET=
if [[ "${TEST_NAME_BASE}" == *-globalcfg ]]; then
    create_test_global_config "" "
[scheduler]
    [[events]]
        handlers = echo 'Your %(workflow)s workflow has a %(event)s event and URL %(workflow_url)s and workflow-priority as %(workflow-priority)s and workflow-UUID as %(uuid)s.'
        handler events = startup"
    OPT_SET='-s GLOBALCFG=True'
fi

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate ${OPT_SET} "${WORKFLOW_NAME}"
# shellcheck disable=SC2086
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach ${OPT_SET} "${WORKFLOW_NAME}"

LOGD="$RUN_DIR/${WORKFLOW_NAME}/log"
WORKFLOW_UUID="$(sqlite3 "${LOGD}/db" "SELECT value FROM workflow_params WHERE key=='uuid_str'")"
LOG_FILE="${LOGD}/scheduler/log"
grep_ok "\\[('workflow-event-handler-00', 'startup') ret_code\\] 0" "${LOG_FILE}"
grep_ok "\\[('workflow-event-handler-00', 'startup') out\\] Your ${WORKFLOW_NAME} workflow has a startup event and URL http://myworkflows.com/${WORKFLOW_NAME}.html and workflow-priority as HIGH and workflow-UUID as ${WORKFLOW_UUID}." "${LOG_FILE}"

purge
exit
