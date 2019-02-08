#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Test for "cylc review", jobs list, task status.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python2 -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 16
#-------------------------------------------------------------------------------
# Initialise, validate and run a suite for testing with
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
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
# Data transfer output check for a specific suite's jobs page

# Key variable for core tests up to end of file
TASKJOBS_URL="${TEST_CYLC_WS_URL}/taskjobs/${USER}?suite=${ESC_SUITE_NAME}&form=json"

TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs"
run_ok "${TEST_NAME}" curl "${TASKJOBS_URL}"
FOO1="{'cycle': '20000101T0000Z', 'name': 'foo', 'submit_num': 1}"
FOO2="{'cycle': '20000101T0000Z', 'name': 'foo', 'submit_num': 2}"
FOO3="{'cycle': '20000101T0000Z', 'name': 'foo', 'submit_num': 3}"
BAR1="{'cycle': '20000101T0000Z', 'name': 'bar', 'submit_num': 1}"
BAR2="{'cycle': '20000101T0000Z', 'name': 'bar', 'submit_num': 2}"
BAR3="{'cycle': '20000101T0000Z', 'name': 'bar', 'submit_num': 3}"
BAZ1="{'cycle': '20000101T0000Z', 'name': 'baz', 'submit_num': 1}"
BAZ2="{'cycle': '20000101T0000Z', 'name': 'baz', 'submit_num': 2}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
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
# Data transfer output check for suite's job page, job status filters
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-failed"
run_ok "${TEST_NAME}" curl "${TASKJOBS_URL}&job_status=failed"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('job_status',), 'failed']" \
    "[('of_n_entries',), 6]"

TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-submission-failed-and-failed"
run_ok "${TEST_NAME}" curl "${TASKJOBS_URL}&job_status=submission-failed,failed"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('job_status',), 'submission-failed,failed']" \
    "[('of_n_entries',), 7]"

TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-succeeded"
run_ok "${TEST_NAME}" curl "${TASKJOBS_URL}&job_status=succeeded"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('job_status',), 'succeeded']" \
    "[('of_n_entries',), 2]"

TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-succeeded-failed"
run_ok "${TEST_NAME}" curl "${TASKJOBS_URL}&job_status=succeeded,failed"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('job_status',), 'succeeded,failed']" \
    "[('of_n_entries',), 8]"
#-------------------------------------------------------------------------------
# Data transfer output check for suite's job page, task status filters
TEST_NAME="${TEST_NAME_BASE}-200-curl-task-succeeded"
run_ok "${TEST_NAME}" curl "${TASKJOBS_URL}&task_status=succeeded"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('of_n_entries',), 5]"

TEST_NAME="${TEST_NAME_BASE}-200-curl-task-succeeded-job-failed"
run_ok "${TEST_NAME}" curl "${TASKJOBS_URL}&task_status=succeeded&job_status=failed"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('of_n_entries',), 2]"
#-------------------------------------------------------------------------------
# Tidy up - note suite trivial so stops early on by itself
purge_suite "${SUITE_NAME}"
cylc_ws_kill
exit
