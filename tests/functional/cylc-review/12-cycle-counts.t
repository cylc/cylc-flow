#!/bin/bash
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
# Test for "cylc review", cycles list, paging.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
requires_cherrypy

set_test_number 4
#-------------------------------------------------------------------------------
# Initialise, validate and run a suite for testing with
init_workflow "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[scheduler]
    UTC mode = True
[scheduling]
    initial cycle point = 20100101T0000Z
    final cycle point = 20100101T0000Z
    [[dependencies]]
        T00 = foo => bar
        T06 = bar[-PT6H] => baz
[runtime]
    [[foo]]
        script = cylc stop $CYLC_WORKFLOW_NAME bar.20100101T0000Z; sleep 5
    [[bar, baz]]
        script = true
__SUITE_RC__

TEST_NAME=$TEST_NAME_BASE-validate
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

cylc play --no-detach --debug "${WORKFLOW_NAME}" 2>'/dev/null'
#-------------------------------------------------------------------------------
# Initialise WSGI application for the cylc review web service
cylc_ws_init 'cylc' 'review'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi

# Set up standard URL escaping of forward slashes in 'cylctb-' suite names.
# shellcheck disable=SC2001
ESC_WORKFLOW_NAME="$(echo "${WORKFLOW_NAME}" | sed 's|/|%2F|g')"
#-------------------------------------------------------------------------------
# Data transfer output check for a suite's cycles page, sorted by time_desc
TEST_NAME_PREFIX="${TEST_NAME_BASE}-200-curl-cycles-page-"
TEST_NAME="${TEST_NAME_PREFIX}1"
PAGE_OPT="&page=1&per_page=3"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/cycles/${USER}/${ESC_WORKFLOW_NAME}?form=json${PAGE_OPT}"

# N.B. Extra cycle at the end, due to spawn-held task beyond final cycle point
cylc_ws_json_greps "${TEST_NAME_PREFIX}1.stdout" "${TEST_NAME_PREFIX}1.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 3]" \
    "[('of_n_entries',), 1]" \
    "[('entries', 0, 'cycle'), '20100101T0000Z']"
#-------------------------------------------------------------------------------
# Tidy up - note suite terminates by itself with 'stop' task
purge "${WORKFLOW_NAME}"
cylc_ws_kill
exit
