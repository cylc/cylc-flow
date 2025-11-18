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
# Test for "cylc review", links to job logs in tar
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
requires_cherrypy

set_test_number 8
#-------------------------------------------------------------------------------
# Initialise, validate and run a suite for testing with
init_workflow "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[scheduler]
    UTC mode = True
    [[events]]
        stall timeout = PT0S
        abort on stall timeout = true
[scheduling]
    initial cycle point = 1999
    final cycle point = 2000
    [[dependencies]]
        P1Y = echo1 & echo2
[runtime]
    [[echo1]]
        script = echo 1
    [[echo2]]
        script = echo 2
__SUITE_RC__

TEST_NAME=$TEST_NAME_BASE-validate
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

cylc play --debug --no-detach "${WORKFLOW_NAME}" 2>'/dev/null'
#-------------------------------------------------------------------------------
# Initialise WSGI application for the cylc review web service
TEST_NAME="${TEST_NAME_BASE}-ws-init"
cylc_ws_init 'cylc' 'review'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi

# Set up standard URL escaping of forward slashes in 'cylctb-' suite names.
# shellcheck disable=SC2001
ESC_WORKFLOW_NAME="$(echo "${WORKFLOW_NAME}" | sed 's|/|%2F|g')"
#-------------------------------------------------------------------------------
# Data transfer output check for a 'tar.gz' format log file job path
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs"

ECHO1="{'cycle': '19990101T0000Z', 'name': 'echo1', 'submit_num': 1}"
ECHO1_JOB='job/19990101T0000Z/echo1/01/job'
ECHO2="{'cycle': '19990101T0000Z', 'name': 'echo2', 'submit_num': 1}"
ECHO2_JOB='job/19990101T0000Z/echo2/01/job'
TAR_FILE='job-19990101T0000Z.tar.gz'

(cd "${WORKFLOW_RUN_DIR}/log" && tar -czf "${TAR_FILE}" 'job/19990101T0000Z')
rm -fr "${WORKFLOW_RUN_DIR}/log/job/19990101T0000Z"

run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/taskjobs/${USER}/${ESC_WORKFLOW_NAME}?form=json"

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
    "${TEST_CYLC_WS_URL}/taskjobs/${USER}/${ESC_WORKFLOW_NAME}?form=json&tasks=echo1"

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
    "${TEST_CYLC_WS_URL}/taskjobs/${USER}/${ESC_WORKFLOW_NAME}?form=json&tasks=echo2"

cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('entries', ${ECHO2}, 'logs', 'job', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.err', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.out', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job', 'path_in_tar'), '${ECHO2_JOB}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.err', 'path_in_tar'), '${ECHO2_JOB}.err']" \
    "[('entries', ${ECHO2}, 'logs', 'job.out', 'path_in_tar'), '${ECHO2_JOB}.out']"
#-------------------------------------------------------------------------------
# Tidy up - note suite trivial so stops early on by itself
purge "${WORKFLOW_NAME}"
cylc_ws_kill
exit
