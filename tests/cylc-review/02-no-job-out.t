#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
# Test for "cylc review", behaviour of job entry with no "job.out".
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 4
#-------------------------------------------------------------------------------
# Initialise, validate and run a suite for testing with
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME

cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null'

# Remove the "job.out" entry from the suite's public database.
sqlite3 "${TEST_DIR}/log/db" \
    'DELETE FROM task_job_logs WHERE filename=="job.out";' 2>'/dev/null' || true
#-------------------------------------------------------------------------------
# Initialise WSGI application for the cylc review web service
cylc_ws_init 'cylc' 'review'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi

# Set up standard URL escaping of forward slashes in 'cylctb-' suite names.
ESC_SUITE_NAME="$(echo ${SUITE_NAME} | sed 's|/|%2F|g')"
#-------------------------------------------------------------------------------
# Data transfer output check for case with no job output publicly viewable
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs"
run_ok "${TEST_NAME}" \
    curl "${TEST_CYLC_WS_URL}/jobs/${USER}?suite=${ESC_SUITE_NAME}&form=json"

FOO0="{'cycle': '20000101T0000Z', 'name': 'foo0', 'submit_num': 1}"
FOO0_OUT='log/job/20000101T0000Z/foo0/01/job.out'
FOO0_OUT_MTIME=$(stat -c'%Y' "${SUITE_RUN_DIR}/${FOO0_OUT}")
FOO0_OUT_SIZE=$(stat -c'%s' "${SUITE_RUN_DIR}/${FOO0_OUT}")

cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('entries', ${FOO0}, 'logs', 'job.out', 'path'), '${FOO0_OUT}']" \
    "[('entries', ${FOO0}, 'logs', 'job.out', 'size'), ${FOO0_OUT_SIZE}]" \
    "[('entries', ${FOO0}, 'logs', 'job.out', 'mtime'), ${FOO0_OUT_MTIME}]" \
    "[('entries', ${FOO0}, 'logs', 'job.out', 'exists'), True]"
#-------------------------------------------------------------------------------
# Tidy up - note suite trivial so stops early on by itself
purge_suite "${SUITE_NAME}"
cylc_ws_kill
exit
