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
# Test for "cylc nameless", cycles/taskjobs list, suite server host:port.
# Require a version of cylc with cylc/cylc#1705 merged in.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 6
#-------------------------------------------------------------------------------
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
#!Jinja2
[cylc]
    [[events]]
        timeout = PT2M
        abort on timeout = True
[scheduling]
    [[dependencies]]
        graph = foo
__SUITE_RC__

TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --debug --no-detach $SUITE_NAME 2>'/dev/null' &
#-------------------------------------------------------------------------------
# Initialise WSGI application for the cylc nameless web service
TEST_NAME="${TEST_NAME_BASE}-ws-init"
cylc_ws_init 'cylc' 'nameless'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi
#-------------------------------------------------------------------------------
# Check a suite's host and port are correctly determined
export CYLC_CONF_PATH=
SUITE_PID="$!"
SRV_D="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/.service"
CONTACT="${SRV_D}/contact"
poll '!' test -s "${CONTACT}"
sleep 1

PORT="$(awk -F= '$1 ~ /CYLC_SUITE_PORT/ {print $2}' "${CONTACT}")"
HOST="$(awk -F= '$1 ~ /CYLC_SUITE_HOST/ {print $2}' "${CONTACT}")"
HOST=${HOST%%.*} # strip domain

if [[ -n "${HOST}" && -n "${PORT}" ]]; then
    for METHOD in 'cycles' 'jobs'; do
        TEST_NAME="${TEST_NAME_BASE}-ws-json-${METHOD}"
        run_ok "${TEST_NAME}" curl \
            "${TEST_CYLC_WS_URL}/${METHOD}/${USER}/${SUITE_NAME}?form=json"
        cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
            "[('states', 'server',), '${HOST}:${PORT}']"
    done
else
    skip 4 'Cannot determine suite host or port'
fi
#-------------------------------------------------------------------------------
# Tidy up
purge_suite "${SUITE_NAME}"
cylc_ws_kill
exit
