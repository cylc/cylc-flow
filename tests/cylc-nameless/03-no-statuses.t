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
# Test for "cylc nameless", jobs list no statuses filter logic, #1762.
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
TEST_DIR="$(mktemp -d --tmpdir="${HOME}/cylc-run" "rtb-rose-bush-03-XXXXXXXX")"
SUITE_NAME="$(basename "${TEST_DIR}")"
cp -pr "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/"* "${TEST_DIR}"
export CYLC_CONF_PATH=
cylc register "${SUITE_NAME}" "${TEST_DIR}"
cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null'

#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs"
FILTERS='&no_status=active&no_status=fail'
run_ok "${TEST_NAME}" \
    curl "${TEST_CYLC_WS_URL}/jobs/${USER}/${SUITE_NAME}?form=json${FILTERS}"
FOO="{'cycle': '20000101T0000Z', 'name': 'foo', 'submit_num': 1}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('of_n_entries',), 1]" \
    "[('entries', ${FOO}, 'task_status'), 'succeeded']"

#-------------------------------------------------------------------------------
# Tidy up
cylc_ws_kill
rm -fr "${TEST_DIR}" 2>'/dev/null'
exit 0
