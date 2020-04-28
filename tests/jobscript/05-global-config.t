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
# Test that global config is used search for poll
. "$(dirname "${0}")/test_header"
#-------------------------------------------------------------------------------
skip_darwin 'atrun hard to configure on Mac OS'
set_test_number 6
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
create_test_globalrc '
[hosts]
   [[localhost]]
        task communication method = poll
        execution polling intervals = PT0.2M, PT0.1M
        submission polling intervals = PT0.2M, PT0.1M'

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
LOG_FILE="${SUITE_RUN_DIR}/log/suite/log"

PRE_MSG='-health check settings:'
for STAGE in 'submission' 'execution'; do
    for A_TASK in 'foo' 'bar'; do
        POLL_INT='PT6S,'
        if [[ "${A_TASK}" == 'foo' ]]; then
            POLL_INT='PT12S,PT6S,'
        elif [[ "${STAGE}" == 'execution' ]]; then
            POLL_INT='PT18S,2\*PT12S,PT6S,'
        fi
        POST_MSG=".*, polling intervals=${POLL_INT}..."
        grep_ok "\[${A_TASK}\.1\] ${PRE_MSG} ${STAGE}${POST_MSG}" "${LOG_FILE}"
    done
done
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
