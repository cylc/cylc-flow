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
# Test for "rose bush", jobs list, sort by queue/run duration, time
# submit/run/run exit.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

tests 13

ROSE_CONF_PATH= rose_ws_init 'rose' 'bush'
if [[ -z "${TEST_ROSE_WS_PORT}" ]]; then
    exit 1
fi

#-------------------------------------------------------------------------------
# Run a quick cylc suite
mkdir -p "${HOME}/cylc-run"
SUITE_DIR="$(mktemp -d --tmpdir="${HOME}/cylc-run" "rtb-rose-bush-04-XXXXXXXX")"
SUITE_NAME="$(basename "${SUITE_DIR}")"
cp -pr "${TEST_SOURCE_DIR}/${TEST_KEY_BASE}/"* "${SUITE_DIR}"
export CYLC_CONF_PATH=
cylc register "${SUITE_NAME}" "${SUITE_DIR}"
cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null' \
    || cat "${SUITE_DIR}/log/suite/err" >&2

#-------------------------------------------------------------------------------
ORDER='time_submit'
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-${ORDER}"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/taskjobs/${USER}/${SUITE_NAME}?form=json&order=${ORDER}"
# Note: only qux submit time order is reliable, the others are submitted at the
# same time, in any order.
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'qux']"

#-------------------------------------------------------------------------------
ORDER='time_run_desc'
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-${ORDER}"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/taskjobs/${USER}/${SUITE_NAME}?form=json&order=${ORDER}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'qux']" \
    "[('entries', 1, 'name'), 'bar']" \
    "[('entries', 2, 'name'), 'baz']" \
    "[('entries', 3, 'name'), 'foo']"

#-------------------------------------------------------------------------------
ORDER='time_run_exit_desc'
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-${ORDER}"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/taskjobs/${USER}/${SUITE_NAME}?form=json&order=${ORDER}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'qux']" \
    "[('entries', 1, 'name'), 'baz']" \
    "[('entries', 2, 'name'), 'bar']" \
    "[('entries', 3, 'name'), 'foo']"

#-------------------------------------------------------------------------------
ORDER='duration_queue_desc'
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-${ORDER}"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/taskjobs/${USER}/${SUITE_NAME}?form=json&order=${ORDER}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'bar']" \
    "[('entries', 1, 'name'), 'baz']" \
    "[('entries', 2, 'name'), 'foo']" \
    "[('entries', 3, 'name'), 'qux']"

#-------------------------------------------------------------------------------
ORDER='duration_run_desc'
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-${ORDER}"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/taskjobs/${USER}/${SUITE_NAME}?form=json&order=${ORDER}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'baz']" \
    "[('entries', 1, 'name'), 'foo']" \
    "[('entries', 2, 'name'), 'qux']" \
    "[('entries', 3, 'name'), 'bar']"

#-------------------------------------------------------------------------------
ORDER='duration_queue_run_desc'
TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-${ORDER}"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/taskjobs/${USER}/${SUITE_NAME}?form=json&order=${ORDER}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('order',), '${ORDER}']" \
    "[('entries', 0, 'name'), 'baz']" \
    "[('entries', 1, 'name'), 'bar']" \
    "[('entries', 2, 'name'), 'foo']" \
    "[('entries', 3, 'name'), 'qux']"
#-------------------------------------------------------------------------------
# Tidy up
rose_ws_kill
rm -fr "${SUITE_DIR}" 2>'/dev/null'
exit 0
