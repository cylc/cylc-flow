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
# Test poll intervals is used from both global.cylc and flow.cylc
. "$(dirname "${0}")/test_header"
#-------------------------------------------------------------------------------
set_test_number 6
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
create_test_global_config "
[platforms]
   [[$CYLC_TEST_PLATFORM]]
        communication method = poll
        execution polling intervals = 10*PT6S
        submission polling intervals = 10*PT6S
"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
LOG_FILE="${WORKFLOW_RUN_DIR}/log/scheduler/log"

PRE_MSG='health:'
POST_MSG='.*, polling intervals=10\*PT6S...'
for INDEX in 1 2; do
    for STAGE in 'submission' 'execution'; do
        grep_ok "1/t${INDEX}.* ${PRE_MSG} ${STAGE}${POST_MSG}" "${LOG_FILE}" -E
    done
done
#-------------------------------------------------------------------------------
purge
exit
