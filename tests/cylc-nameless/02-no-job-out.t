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
# Test for "cylc nameless", behaviour of job entry with no "job.stdout".
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 3

ROSE_CONF_PATH= cylc_ws_init 'cylc' 'nameless'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi

#-------------------------------------------------------------------------------
# Run a quick cylc suite
mkdir -p "${HOME}/cylc-run"
TEST_DIR="$(mktemp -d --tmpdir="${HOME}/cylc-run" "ctb-cylc-nameless-02-XXXXXXXX")"
SUITE_NAME="$(basename "${TEST_DIR}")"
cp -pr "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/"* "${TEST_DIR}"
export CYLC_CONF_PATH=
cylc register "${SUITE_NAME}" "${TEST_DIR}"
cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null' \
    || cat "${TEST_DIR}/log/suite/err" >&2

# Remove the "job.stdout" entry from the suite's public database.
sqlite3 "${TEST_DIR}/log/db" \
    'DELETE FROM task_job_logs WHERE filename=="job.stdout";' 2>'/dev/null' || true

#-------------------------------------------------------------------------------

TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs"
run_ok "${TEST_NAME}" \
    curl "${TEST_CYLC_WS_URL}/taskjobs/${USER}/${SUITE_NAME}?form=json"
FOO0="{'cycle': '20000101T0000Z', 'name': 'foo0', 'submit_num': 1}"
FOO0_OUT='log/job/20000101T0000Z/foo0/01/job.stdout'
FOO0_OUT_MTIME=$(stat -c'%Y' "${TEST_DIR}/${FOO0_OUT}")
FOO0_OUT_SIZE=$(stat -c'%s' "${TEST_DIR}/${FOO0_OUT}")
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('entries', ${FOO0}, 'logs', 'job.stdout', 'path'), '${FOO0_OUT}']" \
    "[('entries', ${FOO0}, 'logs', 'job.stdout', 'size'), ${FOO0_OUT_SIZE}]" \
    "[('entries', ${FOO0}, 'logs', 'job.stdout', 'mtime'), ${FOO0_OUT_MTIME}]" \
    "[('entries', ${FOO0}, 'logs', 'job.stdout', 'exists'), True]"

#-------------------------------------------------------------------------------
# Tidy up
cylc_ws_kill
rm -fr "${TEST_DIR}" 2>'/dev/null'
exit 0
