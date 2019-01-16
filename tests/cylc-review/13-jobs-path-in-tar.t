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
# Test for "cylc review", links to job logs in tar
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python2 -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 8
#-------------------------------------------------------------------------------
# Initialise, validate and run a suite for testing with
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
#!Jinja2
[cylc]
    UTC mode = True
    abort if any task fails = True
[scheduling]
    initial cycle point = 1999
    final cycle point = 2000
    [[dependencies]]
        [[[P1Y]]]
            graph = echo1 & echo2
[runtime]
    [[echo1]]
        script = echo 1
    [[echo2]]
        script = echo 2
__SUITE_RC__

TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME

cylc run --debug --no-detach $SUITE_NAME 2>'/dev/null'
#-------------------------------------------------------------------------------
# Initialise WSGI application for the cylc review web service
TEST_NAME="${TEST_NAME_BASE}-ws-init"
cylc_ws_init 'cylc' 'review'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi

# Set up standard URL escaping of forward slashes in 'cylctb-' suite names.
ESC_SUITE_NAME="$(echo ${SUITE_NAME} | sed 's|/|%2F|g')"
#-------------------------------------------------------------------------------
# Data transfer output check for a 'tar.gz' format log file job path
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs"

ECHO1="{'cycle': '19990101T0000Z', 'name': 'echo1', 'submit_num': 1}"
ECHO1_JOB='job/19990101T0000Z/echo1/01/job'
ECHO2="{'cycle': '19990101T0000Z', 'name': 'echo2', 'submit_num': 1}"
ECHO2_JOB='job/19990101T0000Z/echo2/01/job'
TAR_FILE='job-19990101T0000Z.tar.gz'

(cd "${SUITE_RUN_DIR}/log" && tar -czf "${TAR_FILE}" 'job/19990101T0000Z')
rm -fr "${SUITE_RUN_DIR}/log/job/19990101T0000Z"

run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/jobs/${USER}/${ESC_SUITE_NAME}?form=json"

cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('entries', ${ECHO1}, 'logs', 'job', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO1}, 'logs', 'job.err', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO1}, 'logs', 'job.out', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO1}, 'logs', 'job', 'path_in_tar'), '${ECHO1_JOB}']" \
    "[('entries', ${ECHO1}, 'logs', 'job.err', 'path_in_tar'), '${ECHO1_JOB}.err']" \
    "[('entries', ${ECHO1}, 'logs', 'job.out', 'path_in_tar'), '${ECHO1_JOB}.out']" \
    "[('entries', ${ECHO2}, 'logs', 'job', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.err', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.out', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job', 'path_in_tar'), '${ECHO2_JOB}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.err', 'path_in_tar'), '${ECHO2_JOB}.err']" \
    "[('entries', ${ECHO2}, 'logs', 'job.out', 'path_in_tar'), '${ECHO2_JOB}.out']"
#-------------------------------------------------------------------------------
# Data transfer output check for tar job path, 'echo1' task check
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-tasks-1"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/jobs/${USER}/${ESC_SUITE_NAME}?form=json&tasks=echo1"

cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('entries', ${ECHO1}, 'logs', 'job', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO1}, 'logs', 'job.err', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO1}, 'logs', 'job.out', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO1}, 'logs', 'job', 'path_in_tar'), '${ECHO1_JOB}']" \
    "[('entries', ${ECHO1}, 'logs', 'job.err', 'path_in_tar'), '${ECHO1_JOB}.err']" \
    "[('entries', ${ECHO1}, 'logs', 'job.out', 'path_in_tar'), '${ECHO1_JOB}.out']"
#-------------------------------------------------------------------------------
# Data transfer output check for tar job path, 'echo2' task check
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-tasks-2"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/jobs/${USER}/${ESC_SUITE_NAME}?form=json&tasks=echo2"

cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('entries', ${ECHO2}, 'logs', 'job', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.err', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.out', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job', 'path_in_tar'), '${ECHO2_JOB}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.err', 'path_in_tar'), '${ECHO2_JOB}.err']" \
    "[('entries', ${ECHO2}, 'logs', 'job.out', 'path_in_tar'), '${ECHO2_JOB}.out']"
#-------------------------------------------------------------------------------
# Tidy up - note suite trivial so stops early on by itself
purge_suite "${SUITE_NAME}"
cylc_ws_kill
exit
