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
# Tests for "rose bush", "logo", "title" and "host" settings.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

tests 9

mkdir 'conf'
cat >'conf/rose.conf' <<'__ROSE_CONF__'
[rose-bush]
logo=src="rose-favicon.png" alt="Rose Logo"
title=Humpty Dumpty
host=The Wall
__ROSE_CONF__

ROSE_CONF_PATH="${PWD}/conf" rose_ws_init 'rose' 'bush'
if [[ -z "${TEST_ROSE_WS_PORT}" ]]; then
    exit 1
fi

#-------------------------------------------------------------------------------
# Run a quick cylc suite
mkdir -p "${HOME}/cylc-run"
SUITE_DIR="$(mktemp -d --tmpdir="${HOME}/cylc-run" "rtb-rose-bush-01-XXXXXXXX")"
SUITE_NAME="$(basename "${SUITE_DIR}")"
cp -pr "${TEST_SOURCE_DIR}/${TEST_KEY_BASE}/"* "${SUITE_DIR}"
export CYLC_CONF_PATH=
cylc register "${SUITE_NAME}" "${SUITE_DIR}"
cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null' \
    || cat "${SUITE_DIR}/log/suite/err" >&2

#-------------------------------------------------------------------------------

TEST_KEY="${TEST_KEY_BASE}-200-curl-root-json"
run_pass "${TEST_KEY}" curl "${TEST_ROSE_WS_URL}/?form=json"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('logo',), 'src=\"rose-favicon.png\" alt=\"Rose Logo\"']" \
    "[('title',), 'Humpty Dumpty']" \
    "[('host',), 'The Wall']"

TEST_KEY="${TEST_KEY_BASE}-200-curl-suites-json"
run_pass "${TEST_KEY}" curl "${TEST_ROSE_WS_URL}/suites/${USER}?form=json"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('logo',), 'src=\"rose-favicon.png\" alt=\"Rose Logo\"']" \
    "[('title',), 'Humpty Dumpty']" \
    "[('host',), 'The Wall']"

TEST_KEY="${TEST_KEY_BASE}-200-curl-cycles-json"
run_pass "${TEST_KEY}" \
    curl "${TEST_ROSE_WS_URL}/cycles/${USER}/${SUITE_NAME}?form=json"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('logo',), 'src=\"rose-favicon.png\" alt=\"Rose Logo\"']" \
    "[('title',), 'Humpty Dumpty']" \
    "[('host',), 'The Wall']"

TEST_KEY="${TEST_KEY_BASE}-200-curl-jobs-json"
run_pass "${TEST_KEY}" \
    curl "${TEST_ROSE_WS_URL}/taskjobs/${USER}/${SUITE_NAME}?form=json"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('logo',), 'src=\"rose-favicon.png\" alt=\"Rose Logo\"']" \
    "[('title',), 'Humpty Dumpty']" \
    "[('host',), 'The Wall']"

#-------------------------------------------------------------------------------
# Tidy up
rose_ws_kill
rm -fr "${SUITE_DIR}" 2>'/dev/null'
exit 0
