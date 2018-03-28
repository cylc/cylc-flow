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
# Tests for "cylc nameless", "logo", "title" and "host" settings.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 9

mkdir 'conf'
cat >'conf/rose.conf' <<'__ROSE_CONF__'
[rose-bush]
logo=src="rose-favicon.png" alt="Rose Logo"
title=Humpty Dumpty
host=The Wall
__ROSE_CONF__

ROSE_CONF_PATH="${PWD}/conf" cylc_ws_init 'cylc' 'nameless'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi

#-------------------------------------------------------------------------------
# Run a quick cylc suite
mkdir -p "${HOME}/cylc-run"
TEST_DIR="$(mktemp -d --tmpdir="${HOME}/cylc-run" "ctb-cylc-nameless-01-XXXXXXXX")"
SUITE_NAME="$(basename "${TEST_DIR}")"
cp -pr "${TEST_SOURCE_DIR}/${TEST_KEY_BASE}/"* "${TEST_DIR}"
export CYLC_CONF_PATH=
cylc register "${SUITE_NAME}" "${TEST_DIR}"
cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null' \
    || cat "${TEST_DIR}/log/suite/err" >&2

#-------------------------------------------------------------------------------

TEST_NAME="${TEST_NAME_BASE}-200-curl-root-json"
run_ok "${TEST_NAME}" curl "${TEST_CYLC_WS_URL}/?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('logo',), 'src=\"rose-favicon.png\" alt=\"Rose Logo\"']" \
    "[('title',), 'Humpty Dumpty']" \
    "[('host',), 'The Wall']"

TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-json"
run_ok "${TEST_NAME}" curl "${TEST_CYLC_WS_URL}/suites/${USER}?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('logo',), 'src=\"rose-favicon.png\" alt=\"Rose Logo\"']" \
    "[('title',), 'Humpty Dumpty']" \
    "[('host',), 'The Wall']"

TEST_NAME="${TEST_NAME_BASE}-200-curl-cycles-json"
run_ok "${TEST_NAME}" \
    curl "${TEST_CYLC_WS_URL}/cycles/${USER}/${SUITE_NAME}?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('logo',), 'src=\"rose-favicon.png\" alt=\"Rose Logo\"']" \
    "[('title',), 'Humpty Dumpty']" \
    "[('host',), 'The Wall']"

TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-json"
run_ok "${TEST_NAME}" \
    curl "${TEST_CYLC_WS_URL}/taskjobs/${USER}/${SUITE_NAME}?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('logo',), 'src=\"rose-favicon.png\" alt=\"Rose Logo\"']" \
    "[('title',), 'Humpty Dumpty']" \
    "[('host',), 'The Wall']"

#-------------------------------------------------------------------------------
# Tidy up
cylc_ws_kill
rm -fr "${TEST_DIR}" 2>'/dev/null'
exit 0
