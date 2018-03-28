#!/bin/bash
#-------------------------------------------------------------------------------
# (C) British Crown Copyright 2012-8 Met Office.
#
# This file is part of Rose, a framework for meteorological suites.
#
# Rose is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Rose is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Rose. If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test for "rose bush", links to job logs in tar
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

tests 7

ROSE_CONF_PATH= rose_ws_init 'rose' 'bush'
if [[ -z "${TEST_ROSE_WS_PORT}" ]]; then
    exit 1
fi

cat >'suite.rc' <<'__SUITE_RC__'
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
    [[echo1]]
        script = echo 2
__SUITE_RC__

#-------------------------------------------------------------------------------
# Run a quick cylc suite
mkdir -p "${HOME}/cylc-run"
SUITE_DIR="$(mktemp -d --tmpdir="${HOME}/cylc-run" "rtb-rose-bush-11-XXXXXXXX")"
SUITE_NAME="$(basename "${SUITE_DIR}")"
cp -pr 'suite.rc' "${SUITE_DIR}"
export CYLC_CONF_PATH=
cylc register "${SUITE_NAME}" "${SUITE_DIR}"
cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null'
#-------------------------------------------------------------------------------
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs"
ECHO1="{'cycle': '19990101T0000Z', 'name': 'echo1', 'submit_num': 1}"
ECHO1_JOB='job/19990101T0000Z/echo1/01/job'
ECHO2="{'cycle': '19990101T0000Z', 'name': 'echo2', 'submit_num': 1}"
ECHO2_JOB='job/19990101T0000Z/echo2/01/job'
TAR_FILE='job-19990101T0000Z.tar.gz'
(cd "${SUITE_DIR}/log" && tar -czf "${TAR_FILE}" 'job/19990101T0000Z')
rm -fr "${SUITE_DIR}/log/job/19990101T0000Z"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/jobs/${USER}/${SUITE_NAME}?form=json"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
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
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-tasks-1"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/jobs/${USER}/${SUITE_NAME}?form=json&tasks=echo1"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('entries', ${ECHO1}, 'logs', 'job', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO1}, 'logs', 'job.err', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO1}, 'logs', 'job.out', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO1}, 'logs', 'job', 'path_in_tar'), '${ECHO1_JOB}']" \
    "[('entries', ${ECHO1}, 'logs', 'job.err', 'path_in_tar'), '${ECHO1_JOB}.err']" \
    "[('entries', ${ECHO1}, 'logs', 'job.out', 'path_in_tar'), '${ECHO1_JOB}.out']"
#-------------------------------------------------------------------------------
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-tasks-2"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/jobs/${USER}/${SUITE_NAME}?form=json&tasks=echo2"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('entries', ${ECHO2}, 'logs', 'job', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.err', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.out', 'path'), 'log/${TAR_FILE}']" \
    "[('entries', ${ECHO2}, 'logs', 'job', 'path_in_tar'), '${ECHO2_JOB}']" \
    "[('entries', ${ECHO2}, 'logs', 'job.err', 'path_in_tar'), '${ECHO2_JOB}.err']" \
    "[('entries', ${ECHO2}, 'logs', 'job.out', 'path_in_tar'), '${ECHO2_JOB}.out']"
#-------------------------------------------------------------------------------
# Tidy up
rose_ws_kill
rm -fr "${SUITE_DIR}" 2>'/dev/null'
exit 0
