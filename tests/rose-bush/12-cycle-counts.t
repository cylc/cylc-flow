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
# Test for "rose bush", cycles list, paging.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

tests 3

ROSE_CONF_PATH= rose_ws_init 'rose' 'bush'
if [[ -z "${TEST_ROSE_WS_PORT}" ]]; then
    exit 1
fi

#-------------------------------------------------------------------------------
# Run a quick cylc suite
mkdir -p "${HOME}/cylc-run"
SUITE_DIR="$(mktemp -d --tmpdir="${HOME}/cylc-run" "rtb-rose-bush-12-XXXXXXXX")"
SUITE_NAME="$(basename "${SUITE_DIR}")"
cat >"${SUITE_DIR}/suite.rc" <<'__SUITE_RC__'
#!Jinja2
[cylc]
UTC mode = True
[scheduling]
initial cycle point = 20100101T0000Z
final cycle point = 20100101T0000Z
[[dependencies]]
[[[T00]]]
    graph = foo => bar
[[[T06]]]
    graph = bar[-PT6H] => baz
[runtime]
[[foo]]
    script = cylc stop $CYLC_SUITE_NAME bar.20100101T0000Z; sleep 5
[[bar, baz]]
    script = true
__SUITE_RC__
export CYLC_CONF_PATH=
cylc register "${SUITE_NAME}" "${SUITE_DIR}"
cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null' \
    || cat "${SUITE_DIR}/log/suite/err" >&2

#-------------------------------------------------------------------------------
# Sort by time_desc
TEST_KEY_PREFIX="${TEST_KEY_BASE}-200-curl-cycles-page-"
TEST_KEY="${TEST_KEY_PREFIX}1"
PAGE_OPT="&page=1&per_page=3"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/cycles/${USER}/${SUITE_NAME}?form=json${PAGE_OPT}"

# N.B. Extra cycle at the end, due to spawn-held task beyond final cycle point
rose_ws_json_greps "${TEST_KEY_PREFIX}1.out" "${TEST_KEY_PREFIX}1.out" \
    "[('page',), 1]" \
    "[('per_page',), 3]" \
    "[('of_n_entries',), 1]" \
    "[('entries', 0, 'cycle'), '20100101T0000Z']"
#-------------------------------------------------------------------------------
# Tidy up
rose_ws_kill
rm -fr "${SUITE_DIR}" 2>'/dev/null'
exit 0
