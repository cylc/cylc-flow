#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
# Test for "cylc review", jobs list, sort by queue/run duration, time
# submit/run/run exit.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 14
#-------------------------------------------------------------------------------
# Initialise, validate and run a suite for testing with
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME

cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null'
#-------------------------------------------------------------------------------
# Initialise WSGI application for the cylc review web service
cylc_ws_init 'cylc' 'review'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi

# Set up standard URL escaping of forward slashes in 'cylctb-' suite names.
ESC_SUITE_NAME="$(echo ${SUITE_NAME} | sed 's|/|%2F|g')"
#-------------------------------------------------------------------------------
# Data transfer output checks for a specific jobs page, various time-ordering
ORDER='time_submit'
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-${ORDER}"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/taskjobs/${USER}?suite=${ESC_SUITE_NAME}&form=json&order=${ORDER}"
# Note: only qux submit time order is reliable, the others are submitted at the
# same time, in any order.
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'qux']"

ORDER='time_run_desc'
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-${ORDER}"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/taskjobs/${USER}?suite=${ESC_SUITE_NAME}&form=json&order=${ORDER}"

cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'qux']" \
    "[('entries', 1, 'name'), 'bar']" \
    "[('entries', 2, 'name'), 'baz']" \
    "[('entries', 3, 'name'), 'foo']"

ORDER='time_run_exit_desc'
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-${ORDER}"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/taskjobs/${USER}?suite=${ESC_SUITE_NAME}&form=json&order=${ORDER}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'qux']" \
    "[('entries', 1, 'name'), 'baz']" \
    "[('entries', 2, 'name'), 'bar']" \
    "[('entries', 3, 'name'), 'foo']"

ORDER='duration_queue_desc'
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-${ORDER}"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/taskjobs/${USER}?suite=${ESC_SUITE_NAME}&form=json&order=${ORDER}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'bar']" \
    "[('entries', 1, 'name'), 'baz']" \
    "[('entries', 2, 'name'), 'foo']" \
    "[('entries', 3, 'name'), 'qux']"

ORDER='duration_run_desc'
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-${ORDER}"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/taskjobs/${USER}?suite=${ESC_SUITE_NAME}&form=json&order=${ORDER}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'baz']" \
    "[('entries', 1, 'name'), 'foo']" \
    "[('entries', 2, 'name'), 'qux']" \
    "[('entries', 3, 'name'), 'bar']"

ORDER='duration_queue_run_desc'
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-${ORDER}"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/taskjobs/${USER}?suite=${ESC_SUITE_NAME}&form=json&order=${ORDER}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'baz']" \
    "[('entries', 1, 'name'), 'bar']" \
    "[('entries', 2, 'name'), 'foo']" \
    "[('entries', 3, 'name'), 'qux']"
#-------------------------------------------------------------------------------
# Tidy up - note suite trivial so stops early on by itself
purge_suite "${SUITE_NAME}"
cylc_ws_kill
exit
