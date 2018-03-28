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
# Test for "rose bush", jobs list, task status.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

tests 15

ROSE_CONF_PATH= rose_ws_init 'rose' 'bush'
if [[ -z "${TEST_ROSE_WS_PORT}" ]]; then
    exit 1
fi

cat >'suite.rc' <<'__SUITE_RC__'
#!Jinja2
[cylc]
    UTC mode = True
    [[events]]
        abort on stalled = True
[scheduling]
    initial cycle point = 2000
    final cycle point = 2000
    [[dependencies]]
        [[[P1Y]]]
            graph = foo & bar & baz
[runtime]
    [[foo]]
        script = test "${CYLC_TASK_TRY_NUMBER}" -eq 3
        [[[job]]]
            execution retry delays = 3*PT1S
    [[bar]]
        script = false
        [[[job]]]
            execution retry delays = 3*PT1S
    [[baz]]
        env-script = """
trap '' EXIT
if ((${CYLC_TASK_SUBMIT_NUMBER} == 1)); then
    exit
fi
"""
        script = true
        [[[job]]]
            submission retry delays = 3*PT1S
            submission polling intervals = 20*PT3S
__SUITE_RC__

#-------------------------------------------------------------------------------
# Run a quick cylc suite
mkdir -p "${HOME}/cylc-run"
SUITE_DIR="$(mktemp -d --tmpdir="${HOME}/cylc-run" "rtb-rose-bush-10-XXXXXXXX")"
SUITE_NAME="$(basename "${SUITE_DIR}")"
cp -p 'suite.rc' "${SUITE_DIR}"
export CYLC_CONF_PATH=
cylc register "${SUITE_NAME}" "${SUITE_DIR}"
cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null'
TASKJOBS_URL="${TEST_ROSE_WS_URL}/taskjobs/${USER}/${SUITE_NAME}?form=json"
#-------------------------------------------------------------------------------
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs"
run_pass "${TEST_KEY}" curl "${TASKJOBS_URL}"
FOO1="{'cycle': '20000101T0000Z', 'name': 'foo', 'submit_num': 1}"
FOO2="{'cycle': '20000101T0000Z', 'name': 'foo', 'submit_num': 2}"
FOO3="{'cycle': '20000101T0000Z', 'name': 'foo', 'submit_num': 3}"
BAR1="{'cycle': '20000101T0000Z', 'name': 'bar', 'submit_num': 1}"
BAR2="{'cycle': '20000101T0000Z', 'name': 'bar', 'submit_num': 2}"
BAR3="{'cycle': '20000101T0000Z', 'name': 'bar', 'submit_num': 3}"
BAZ1="{'cycle': '20000101T0000Z', 'name': 'baz', 'submit_num': 1}"
BAZ2="{'cycle': '20000101T0000Z', 'name': 'baz', 'submit_num': 2}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('of_n_entries',), 9]" \
    "[('job_status',), None]" \
    "[('entries', ${FOO1}, 'task_status',), 'succeeded']" \
    "[('entries', ${FOO1}, 'run_status',), 1]" \
    "[('entries', ${FOO1}, 'run_signal',), 'EXIT']" \
    "[('entries', ${FOO2}, 'task_status',), 'succeeded']" \
    "[('entries', ${FOO2}, 'run_status',), 1]" \
    "[('entries', ${FOO2}, 'run_signal',), 'EXIT']" \
    "[('entries', ${FOO3}, 'task_status',), 'succeeded']" \
    "[('entries', ${FOO3}, 'run_status',), 0]" \
    "[('entries', ${BAR1}, 'task_status',), 'failed']" \
    "[('entries', ${BAR1}, 'run_status',), 1]" \
    "[('entries', ${BAR1}, 'run_signal',), 'EXIT']" \
    "[('entries', ${BAR2}, 'task_status',), 'failed']" \
    "[('entries', ${BAR2}, 'run_status',), 1]" \
    "[('entries', ${BAR2}, 'run_signal',), 'EXIT']" \
    "[('entries', ${BAR3}, 'task_status',), 'failed']" \
    "[('entries', ${BAR3}, 'run_status',), 1]" \
    "[('entries', ${BAR3}, 'run_signal',), 'EXIT']" \
    "[('entries', ${BAZ1}, 'task_status',), 'succeeded']" \
    "[('entries', ${BAZ1}, 'submit_status',), 1]" \
    "[('entries', ${BAZ1}, 'run_status',), None]" \
    "[('entries', ${BAZ1}, 'run_signal',), None]" \
    "[('entries', ${BAZ2}, 'task_status',), 'succeeded']" \
    "[('entries', ${BAZ2}, 'submit_status',), 0]" \
    "[('entries', ${BAZ2}, 'run_status',), 0]" \
    "[('entries', ${BAZ2}, 'run_signal',), None]"

#-------------------------------------------------------------------------------
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-failed"
run_pass "${TEST_KEY}" curl "${TASKJOBS_URL}&job_status=failed"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('job_status',), 'failed']" \
    "[('of_n_entries',), 6]"
#-------------------------------------------------------------------------------
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-submission-failed-and-failed"
run_pass "${TEST_KEY}" curl "${TASKJOBS_URL}&job_status=submission-failed,failed"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('job_status',), 'submission-failed,failed']" \
    "[('of_n_entries',), 7]"
#-------------------------------------------------------------------------------
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-succeeded"
run_pass "${TEST_KEY}" curl "${TASKJOBS_URL}&job_status=succeeded"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('job_status',), 'succeeded']" \
    "[('of_n_entries',), 2]"
#-------------------------------------------------------------------------------
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-succeeded-failed"
run_pass "${TEST_KEY}" curl "${TASKJOBS_URL}&job_status=succeeded,failed"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('job_status',), 'succeeded,failed']" \
    "[('of_n_entries',), 8]"
#-------------------------------------------------------------------------------
TEST_KEY="${TEST_KEY_BASE}-200-curl-task-succeeded"
run_pass "${TEST_KEY}" curl "${TASKJOBS_URL}&task_status=succeeded"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('of_n_entries',), 5]"
#-------------------------------------------------------------------------------
TEST_KEY="${TEST_KEY_BASE}-200-curl-task-succeeded-job-failed"
run_pass "${TEST_KEY}" curl "${TASKJOBS_URL}&task_status=succeeded&job_status=failed"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('of_n_entries',), 2]"
#-------------------------------------------------------------------------------
# Tidy up
rose_ws_kill
rm -fr "${SUITE_DIR}" 2>'/dev/null'
exit 0
