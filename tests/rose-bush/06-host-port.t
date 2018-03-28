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
# Test for "rose bush", cycles/taskjobs list, suite server host:port.
# Require a version of cylc with cylc/cylc#1705 merged in.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

tests 5

ROSE_CONF_PATH= rose_ws_init 'rose' 'bush'
if [[ -z "${TEST_ROSE_WS_PORT}" ]]; then
    exit 1
fi

#-------------------------------------------------------------------------------
# Run a quick cylc suite
mkdir -p "${HOME}/cylc-run"
SUITE_DIR="$(mktemp -d --tmpdir="${HOME}/cylc-run" "rtb-rose-bush-00-XXXXXXXX")"
SUITE_NAME="$(basename "${SUITE_DIR}")"
cat >"${SUITE_DIR}/suite.rc" <<'__SUITE_RC__'
#!Jinja2
[cylc]
    UTC mode = True
    [[events]]
        timeout = PT2M
        abort on timeout = True
[scheduling]
    initial cycle point = 2000
    final cycle point = 2000
    [[dependencies]]
        [[[P1Y]]]
            graph = loser
[runtime]
    [[loser]]
        script = false
__SUITE_RC__
export CYLC_CONF_PATH=
cylc register "${SUITE_NAME}" "${SUITE_DIR}"
cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null' &
SUITE_PID="$!"
CONTACT="${HOME}/cylc-run/${SUITE_NAME}/.service/contact"
poll '!' test -s "${CONTACT}"
sleep 1
PORT="$(awk -F= '$1 ~ /CYLC_SUITE_PORT/ {print $2}' "${CONTACT}")"
HOST="$(awk -F= '$1 ~ /CYLC_SUITE_HOST/ {print $2}' "${CONTACT}")"
HOST=${HOST%%.*}  # strip domain

if [[ -n "${HOST}" && -n "${PORT}" ]]; then
    for METHOD in 'cycles' 'jobs'; do
        TEST_KEY="${TEST_KEY_BASE}-200-curl-${METHOD}"
        run_pass "${TEST_KEY}" curl \
            "${TEST_ROSE_WS_URL}/${METHOD}/${USER}/${SUITE_NAME}?form=json"
        rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
            "[('states', 'server',), '${HOST}:${PORT}']"
    done
else
    skip 4 'Cannot determine suite host or port'
fi
#-------------------------------------------------------------------------------
# Tidy up
cylc stop "${SUITE_NAME}"
wait "${SUITE_PID}" || cat "${SUITE_DIR}/log/suite/err" >&2
rose_ws_kill
rm -fr "${SUITE_DIR}" 2>'/dev/null'
exit 0
