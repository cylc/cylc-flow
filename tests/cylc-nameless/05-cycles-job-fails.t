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
# Test for "cylc nameless", cycles list, number of failed jobs.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 3

ROSE_CONF_PATH= cylc_ws_init 'rose' 'bush'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi

#-------------------------------------------------------------------------------
# Run a quick cylc suite
mkdir -p "${HOME}/cylc-run"
TEST_DIR="$(mktemp -d --tmpdir="${HOME}/cylc-run" "rtb-rose-bush-05-XXXXXXXX")"
SUITE_NAME="$(basename "${TEST_DIR}")"
cp -pr "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/"* "${TEST_DIR}"
export CYLC_CONF_PATH=
cylc register "${SUITE_NAME}" "${TEST_DIR}"
cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null' \
    || cat "${TEST_DIR}/log/suite/err" >&2

#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-200-curl-cycles"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/cycles/${USER}/${SUITE_NAME}?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('entries', {'cycle': '20000101T0000Z'}, 'n_states', 'success',), 3]" \
    "[('entries', {'cycle': '20000101T0000Z'}, 'n_states', 'job_success',), 2]" \
    "[('entries', {'cycle': '20000101T0000Z'}, 'n_states', 'fail',), 0]" \
    "[('entries', {'cycle': '20000101T0000Z'}, 'n_states', 'job_fail',), 1]"
#-------------------------------------------------------------------------------
# Tidy up
cylc_ws_kill
rm -fr "${TEST_DIR}" 2>'/dev/null'
exit 0
