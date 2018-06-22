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
# Test for "cylc review", cycles/taskjobs list, suite server host:port.
# Require a version of cylc with cylc/cylc#1705 merged in.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 6
#-------------------------------------------------------------------------------
# Initialise, validate and run a suite for testing with
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
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

TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME

export CYLC_CONF_PATH=

# Background to leave sitting in stalled state
cylc run --debug --no-detach $SUITE_NAME 2>'/dev/null' &
#-------------------------------------------------------------------------------
# Initialise WSGI application for the cylc review web service
TEST_NAME="${TEST_NAME_BASE}-ws-init"
cylc_ws_init 'cylc' 'review'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi

# Set up standard URL escaping of forward slashes in 'cylctb-' suite names.
ESC_SUITE_NAME="$(echo ${SUITE_NAME} | sed 's|/|%2F|g')"
#-------------------------------------------------------------------------------
# Data transfer output check for a specific suite's host and port

SRV_D="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/.service"
CONTACT="${SRV_D}/contact"
poll '!' test -s "${CONTACT}"
sleep 1
PORT="$(awk -F= '$1 ~ /CYLC_SUITE_PORT/ {print $2}' "${CONTACT}")"
HOST="$(awk -F= '$1 ~ /CYLC_SUITE_HOST/ {print $2}' "${CONTACT}")"
HOST=${HOST%%.*} # strip domain

if [[ -n "${HOST}" && -n "${PORT}" ]]; then
    for METHOD in 'cycles' 'taskjobs'; do
        TEST_NAME="${TEST_NAME_BASE}-ws-run-${METHOD}"
        URL_NAME="${TEST_CYLC_WS_URL}/${METHOD}/${USER}?suite=${ESC_SUITE_NAME}&form=json"
        run_ok "${TEST_NAME}" curl "${URL_NAME}"
        cylc_ws_json_greps "${TEST_NAME}-json" "${TEST_NAME}.stdout" "[('states', 'server',), '${HOST}:${PORT}']"
    done
else
    skip 4 'Cannot determine suite host or port'
fi
#-------------------------------------------------------------------------------
# Tidy up
cylc stop "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
cylc_ws_kill
exit
