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
# Basic tests for "cylc review".
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python2 -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 64
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
# Data transfer output check for review homepage
TEST_NAME="${TEST_NAME_BASE}-curl-root"
run_ok "${TEST_NAME}" curl -I -s "${TEST_CYLC_WS_URL}"
grep_ok 'HTTP/.* 200 OK' "${TEST_NAME}.stdout"

TEST_NAME="${TEST_NAME_BASE}-200-curl-root-json"
run_ok "${TEST_NAME}" curl "${TEST_CYLC_WS_URL}/?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('cylc_version',), '$(cylc version | cut -d' ' -f 2)']" \
    "[('title',), 'Cylc Review']" \
    "[('host',), '$(hostname)']"
#-------------------------------------------------------------------------------
# Data transfer output check for a specific user's page including non-existent
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites"
run_ok "${TEST_NAME}" curl -I "${TEST_CYLC_WS_URL}/suites/${USER}"
grep_ok 'HTTP/.* 200 OK' "${TEST_NAME}.stdout"

TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-json"
run_ok "${TEST_NAME}" curl "${TEST_CYLC_WS_URL}/suites/${USER}?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('cylc_version',), '$(cylc version | cut -d' ' -f 2)']" \
    "[('title',), 'Cylc Review']" \
    "[('host',), '$(hostname)']" \
    "[('user',), '${USER}']"

TEST_NAME="${TEST_NAME_BASE}-404-curl-suites"
run_ok "${TEST_NAME}" curl -I "${TEST_CYLC_WS_URL}/suites/no-such-user"
grep_ok 'HTTP/.* 404 Not Found' "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
# Connection check for a specific suite's cycles & jobs page
for METHOD in 'cycles' 'jobs'; do
    TEST_NAME="${TEST_NAME_BASE}-200-curl-${METHOD}"
    run_ok "${TEST_NAME}" \
        curl -I "${TEST_CYLC_WS_URL}/${METHOD}/${USER}/${ESC_SUITE_NAME}"
    grep_ok 'HTTP/.* 200 OK' "${TEST_NAME}.stdout"

    TEST_NAME="${TEST_NAME_BASE}-404-1-curl-${METHOD}"
    run_ok "${TEST_NAME}" \
        curl -I "${TEST_CYLC_WS_URL}/${METHOD}/no-such-user/${ESC_SUITE_NAME}"
    grep_ok 'HTTP/.* 404 Not Found' "${TEST_NAME}.stdout"

    TEST_NAME="${TEST_NAME_BASE}-404-2-curl-${METHOD}"
    run_ok "${TEST_NAME}" \
        curl -I "${TEST_CYLC_WS_URL}/${METHOD}/${USER}?suite=no-such-suite"
    grep_ok 'HTTP/.* 404 Not Found' "${TEST_NAME}.stdout"
done
#-------------------------------------------------------------------------------
# Check that waiting tasks appear when "task_status=waiting"
TEST_NAME="${TEST_NAME_BASE}-200-waiting-tasks"

URL_PARAMS='?form=json&task_status=waiting'
run_ok "${TEST_NAME}" \
    curl "${TEST_CYLC_WS_URL}/taskjobs/${USER}/${ESC_SUITE_NAME}${URL_PARAMS}"

FOO2="{'cycle': '20010101T0000Z', 'name': 'foo0', 'submit_num': 0}"
FOO3="{'cycle': '20010101T0000Z', 'name': 'foo1', 'submit_num': 0}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('entries', ${FOO2}, 'events',), [None, None, None]]" \
    "[('entries', ${FOO3}, 'events',), [None, None, None]]"
#-------------------------------------------------------------------------------
# Data transfer output check for a specific suite's cycles & jobs page
TEST_NAME="${TEST_NAME_BASE}-200-curl-cycles"

run_ok "${TEST_NAME}" \
    curl "${TEST_CYLC_WS_URL}/cycles/${USER}/${ESC_SUITE_NAME}?form=json"

cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('cylc_version',), '$(cylc version | cut -d' ' -f 2)']" \
    "[('title',), 'Cylc Review']" \
    "[('host',), '$(hostname)']" \
    "[('user',), '${USER}']" \
    "[('suite',), '${SUITE_NAME}']" \
    "[('page',), 1]" \
    "[('n_pages',), 1]" \
    "[('per_page',), 100]" \
    "[('order',), None]" \
    "[('states', 'is_running',), False]" \
    "[('states', 'is_failed',), False]" \
    "[('of_n_entries',), 1]" \
    "[('entries', {'cycle': '20000101T0000Z'}, 'n_states', 'success',), 2]" \
    "[('entries', {'cycle': '20000101T0000Z'}, 'n_states', 'job_success',), 2]"

TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs"
run_ok "${TEST_NAME}" \
    curl "${TEST_CYLC_WS_URL}/taskjobs/${USER}/${ESC_SUITE_NAME}?form=json"
FOO0="{'cycle': '20000101T0000Z', 'name': 'foo0', 'submit_num': 1}"
FOO0_JOB='log/job/20000101T0000Z/foo0/01/job'
FOO1="{'cycle': '20000101T0000Z', 'name': 'foo1', 'submit_num': 1}"
FOO1_JOB='log/job/20000101T0000Z/foo1/01/job'
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('cylc_version',), '$(cylc version | cut -d' ' -f 2)']" \
    "[('title',), 'Cylc Review']" \
    "[('host',), '$(hostname)']" \
    "[('user',), '${USER}']" \
    "[('suite',), '${SUITE_NAME}']" \
    "[('is_option_on',), False]" \
    "[('page',), 1]" \
    "[('n_pages',), 1]" \
    "[('per_page',), 15]" \
    "[('per_page_default',), 15]" \
    "[('per_page_max',), 300]" \
    "[('cycles',), None]" \
    "[('order',), None]" \
    "[('states', 'is_running',), False]" \
    "[('states', 'is_failed',), False]" \
    "[('of_n_entries',), 2]" \
    "[('entries', ${FOO0}, 'task_status',), 'succeeded']" \
    "[('entries', ${FOO0}, 'host',), '$(hostname -f)']" \
    "[('entries', ${FOO0}, 'submit_method',), 'background']" \
    "[('entries', ${FOO0}, 'logs', 'job', 'path'), '${FOO0_JOB}']" \
    "[('entries', ${FOO0}, 'logs', 'job.err', 'path'), '${FOO0_JOB}.err']" \
    "[('entries', ${FOO0}, 'logs', 'job.out', 'path'), '${FOO0_JOB}.out']" \
    "[('entries', ${FOO0}, 'logs', 'job.01.txt', 'seq_key'), 'job.*.txt']" \
    "[('entries', ${FOO0}, 'logs', 'job.05.txt', 'seq_key'), 'job.*.txt']" \
    "[('entries', ${FOO0}, 'logs', 'job.10.txt', 'seq_key'), 'job.*.txt']" \
    "[('entries', ${FOO0}, 'seq_logs_indexes', 'job.*.txt', '1'), 'job.01.txt']" \
    "[('entries', ${FOO0}, 'seq_logs_indexes', 'job.*.txt', '5'), 'job.05.txt']" \
    "[('entries', ${FOO0}, 'seq_logs_indexes', 'job.*.txt', '10'), 'job.10.txt']" \
    "[('entries', ${FOO0}, 'logs', 'bunch.holly.out', 'seq_key'), 'bunch.*.out']" \
    "[('entries', ${FOO0}, 'logs', 'bunch.iris.out', 'seq_key'), 'bunch.*.out']" \
    "[('entries', ${FOO0}, 'logs', 'bunch.daisy.out', 'seq_key'), 'bunch.*.out']" \
    "[('entries', ${FOO0}, 'seq_logs_indexes', 'bunch.*.out', 'holly'), 'bunch.holly.out']" \
    "[('entries', ${FOO0}, 'seq_logs_indexes', 'bunch.*.out', 'iris'), 'bunch.iris.out']" \
    "[('entries', ${FOO0}, 'seq_logs_indexes', 'bunch.*.out', 'daisy'), 'bunch.daisy.out']" \
    "[('entries', ${FOO0}, 'logs', 'job.trace.2.html', 'seq_key'), 'job.trace.*.html']" \
    "[('entries', ${FOO0}, 'logs', 'job.trace.32.html', 'seq_key'), 'job.trace.*.html']" \
    "[('entries', ${FOO0}, 'logs', 'job.trace.256.html', 'seq_key'), 'job.trace.*.html']" \
    "[('entries', ${FOO0}, 'seq_logs_indexes', 'job.trace.*.html', '2'), 'job.trace.2.html']" \
    "[('entries', ${FOO0}, 'seq_logs_indexes', 'job.trace.*.html', '32'), 'job.trace.32.html']" \
    "[('entries', ${FOO0}, 'seq_logs_indexes', 'job.trace.*.html', '256'), 'job.trace.256.html']" \
    "[('entries', ${FOO1}, 'task_status',), 'succeeded']" \
    "[('entries', ${FOO1}, 'host',), '$(hostname -f)']" \
    "[('entries', ${FOO1}, 'submit_method',), 'background']" \
    "[('entries', ${FOO1}, 'logs', 'job', 'path'), '${FOO1_JOB}']" \
    "[('entries', ${FOO1}, 'logs', 'job.err', 'path'), '${FOO1_JOB}.err']" \
    "[('entries', ${FOO1}, 'logs', 'job.out', 'path'), '${FOO1_JOB}.out']" \
    "[('entries', ${FOO1}, 'logs', 'job.01.txt', 'seq_key'), 'job.*.txt']" \
    "[('entries', ${FOO1}, 'logs', 'job.05.txt', 'seq_key'), 'job.*.txt']" \
    "[('entries', ${FOO1}, 'logs', 'job.10.txt', 'seq_key'), 'job.*.txt']" \
    "[('entries', ${FOO1}, 'seq_logs_indexes', 'job.*.txt', '1'), 'job.01.txt']" \
    "[('entries', ${FOO1}, 'seq_logs_indexes', 'job.*.txt', '5'), 'job.05.txt']" \
    "[('entries', ${FOO1}, 'seq_logs_indexes', 'job.*.txt', '10'), 'job.10.txt']" \
    "[('entries', ${FOO1}, 'logs', 'bunch.holly.out', 'seq_key'), 'bunch.*.out']" \
    "[('entries', ${FOO1}, 'logs', 'bunch.iris.out', 'seq_key'), 'bunch.*.out']" \
    "[('entries', ${FOO1}, 'logs', 'bunch.daisy.out', 'seq_key'), 'bunch.*.out']" \
    "[('entries', ${FOO1}, 'seq_logs_indexes', 'bunch.*.out', 'holly'), 'bunch.holly.out']" \
    "[('entries', ${FOO1}, 'seq_logs_indexes', 'bunch.*.out', 'iris'), 'bunch.iris.out']" \
    "[('entries', ${FOO1}, 'seq_logs_indexes', 'bunch.*.out', 'daisy'), 'bunch.daisy.out']" \
    "[('entries', ${FOO1}, 'logs', 'job.trace.2.html', 'seq_key'), 'job.trace.*.html']" \
    "[('entries', ${FOO1}, 'logs', 'job.trace.32.html', 'seq_key'), 'job.trace.*.html']" \
    "[('entries', ${FOO1}, 'logs', 'job.trace.256.html', 'seq_key'), 'job.trace.*.html']" \
    "[('entries', ${FOO1}, 'seq_logs_indexes', 'job.trace.*.html', '2'), 'job.trace.2.html']" \
    "[('entries', ${FOO1}, 'seq_logs_indexes', 'job.trace.*.html', '32'), 'job.trace.32.html']" \
    "[('entries', ${FOO1}, 'seq_logs_indexes', 'job.trace.*.html', '256'), 'job.trace.256.html']"

#-------------------------------------------------------------------------------
# Data transfer output check for a suite run directory with only a "log/db"
COPY_NAME="${SUITE_NAME}-copy"
cylc register "${COPY_NAME}"

CYLC_RUN_DIR="$(cylc get-global-config --print-run-dir)"
mkdir "${CYLC_RUN_DIR}/${COPY_NAME}/log/"
cp "${SUITE_RUN_DIR}/log/db" "${CYLC_RUN_DIR}/${COPY_NAME}/log/"

ESC_COPY_NAME="$(echo ${COPY_NAME} | sed 's|/|%2F|g')"
run_ok "${TEST_NAME}-bare" \
    curl "${TEST_CYLC_WS_URL}/taskjobs/${USER}?suite=${ESC_COPY_NAME}&form=json"

cylc_ws_json_greps "${TEST_NAME}-bare.stdout" "${TEST_NAME}-bare.stdout" \
    "[('suite',), '${COPY_NAME}']"

for FILE in \
    'log/suite/log' \
    'log/job/20000101T0000Z/foo0/01/job' \
    'log/job/20000101T0000Z/foo0/01/job.out' \
    'log/job/20000101T0000Z/foo1/01/job' \
    'log/job/20000101T0000Z/foo1/01/job.out'
do
    TEST_NAME="${TEST_NAME_BASE}-200-curl-view-$(tr '/' '-' <<<"${FILE}")"
    run_ok "${TEST_NAME}" \
        curl -I "${TEST_CYLC_WS_URL}/view/${USER}/${ESC_SUITE_NAME}?path=${FILE}"
    grep_ok 'HTTP/.* 200 OK' "${TEST_NAME}.stdout"
    MODE='&mode=download'
    run_ok "${TEST_NAME}-download" \
        curl "${TEST_CYLC_WS_URL}/view/${USER}/${ESC_SUITE_NAME}?path=${FILE}${MODE}"
    cmp_ok "${TEST_NAME}-download.stdout" \
        "${TEST_NAME}-download.stdout" "${HOME}/cylc-run/${SUITE_NAME}/${FILE}"
done

TEST_NAME="${TEST_NAME_BASE}-404-curl-view-garbage"
run_ok "${TEST_NAME}" \
    curl -I \
    "${TEST_CYLC_WS_URL}/view/${USER}/${ESC_SUITE_NAME}?path=log/of/minus-one"
grep_ok 'HTTP/.* 404 Not Found' "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
# Test of the file search feature
TEST_NAME="${TEST_NAME_BASE}-200-curl-viewsearch"
FILE='log/job/20000101T0000Z/foo1/01/job.out'
MODE="&mode=text"
URL="${TEST_CYLC_WS_URL}/viewsearch/${USER}/${ESC_SUITE_NAME}?path=${FILE}${MODE}\
&search_mode=TEXT&search_string=Hello%20from"

run_ok "${TEST_NAME}" curl -I "${URL}"
grep_ok 'HTTP/.* 200 OK' "${TEST_NAME}.stdout"

TEST_NAME="${TEST_NAME_BASE}-200-curl-viewsearch-download"
run_ok "${TEST_NAME}" \
    curl "${URL}"
grep_ok '<span class="highlight">Hello from</span>' \
    "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
# Test requesting a file outside of the suite directory tree:
# 1. By absolute path.
TEST_NAME="${TEST_NAME_BASE}-403-curl-view-outside-absolute"
run_ok "${TEST_NAME}" \
    curl -I \
    "${TEST_CYLC_WS_URL}/view/${USER}/${ESC_SUITE_NAME}?path=/dev/null"
grep_ok 'HTTP/.* 403 Forbidden' "${TEST_NAME}.stdout"
# 2. By absolute path to imaginary suite directory.
TEST_NAME="${TEST_NAME_BASE}-403-curl-view-outside-imag"
IMG_TEST_DIR="${SUITE_RUN_DIR}-imag"
mkdir -p "${IMG_TEST_DIR}"
echo 'Welcome to the imaginary suite.'>"${IMG_TEST_DIR}/welcome.txt"
run_ok "${TEST_NAME}" \
    curl -I \
    "${TEST_CYLC_WS_URL}/view/${USER}/${ESC_SUITE_NAME}?path=${IMG_TEST_DIR}/welcome.txt"
grep_ok 'HTTP/.* 403 Forbidden' "${TEST_NAME}.stdout"
# 3. By relative path.
TEST_NAME="${TEST_NAME_BASE}-403-curl-view-outside-relative"
run_ok "${TEST_NAME}" \
    curl -I \
    "${TEST_CYLC_WS_URL}/view/${USER}/${ESC_SUITE_NAME}?path=../$(basename $IMG_TEST_DIR)/welcome.txt"
grep_ok 'HTTP/.* 403 Forbidden' "${TEST_NAME}.stdout"
rm "${IMG_TEST_DIR}/welcome.txt"
rmdir "${IMG_TEST_DIR}"
#-------------------------------------------------------------------------------
# Tidy up - note suite trivial so stops early on by itself
purge_suite "${SUITE_NAME}"
cylc_ws_kill
exit
