#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Test for "cylc review", jobs list, fuzzy time flag.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python2 -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 14
#-------------------------------------------------------------------------------
# Initialise, validate and run a suite for testing with
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
#!Jinja2
[cylc]
    UTC mode = True
[scheduling]
    initial cycle point = 2000
    final cycle point = 2000
    [[dependencies]]
        [[[P1Y]]]
            graph = foo
[runtime]
    [[foo]]
        script = true
__SUITE_RC__

TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME

cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null'
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
# Data transfer output check for a specific user's/suite's 'fuzzy time'
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('no_fuzzy_time',), '0']"

TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-no-fuzzy-time"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json&no_fuzzy_time=1"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('no_fuzzy_time',), '1']"

TEST_NAME="${TEST_NAME_BASE}-200-curl-cycles"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/cycles/${USER}/${ESC_SUITE_NAME}?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('no_fuzzy_time',), '0']"

TEST_NAME="${TEST_NAME_BASE}-200-curl-cycles-no-fuzzy-time"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/cycles/${USER}/${ESC_SUITE_NAME}?form=json&no_fuzzy_time=1"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('no_fuzzy_time',), '1']"

TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/taskjobs/${USER}/${ESC_SUITE_NAME}?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('no_fuzzy_time',), '0']"

TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-no-fuzzy-time"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/taskjobs/${USER}/${ESC_SUITE_NAME}?form=json&no_fuzzy_time=1"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('no_fuzzy_time',), '1']"
#-------------------------------------------------------------------------------
# Tidy up - note suite trivial so stops early on by itself
purge_suite "${SUITE_NAME}"
cylc_ws_kill
exit