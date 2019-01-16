#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
# Tests for "cylc review", "logo", "title" and "host" settings.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python2 -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 10
#-------------------------------------------------------------------------------
# Initialise, validate and run a suite for testing with
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME

cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null'
#-------------------------------------------------------------------------------
# Initialise WSGI application for the cylc review web service
cylc_ws_init 'cylc' 'review'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi

# Set up standard URL escaping of forward slashes in 'cylctb-' suite names.
ESC_SUITE_NAME="$(echo ${SUITE_NAME} | sed 's|/|%2F|g')"
#-------------------------------------------------------------------------------
# Basic data transfer output check
TEST_NAME="${TEST_NAME_BASE}-200-curl-root-json"
run_ok "${TEST_NAME}" curl "${TEST_CYLC_WS_URL}/?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('logo',), 'cylc-logo.png']" \
    "[('title',), 'Cylc Review']" \
    "[('host',), '$(hostname)']"

TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-json"
run_ok "${TEST_NAME}" curl "${TEST_CYLC_WS_URL}/suites/${USER}?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('logo',), 'cylc-logo.png']" \
    "[('title',), 'Cylc Review']" \
    "[('host',), '$(hostname)']"

TEST_NAME="${TEST_NAME_BASE}-200-curl-cycles-json"
run_ok "${TEST_NAME}" \
    curl "${TEST_CYLC_WS_URL}/cycles/${USER}/${ESC_SUITE_NAME}?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('logo',), 'cylc-logo.png']" \
    "[('title',), 'Cylc Review']" \
    "[('host',), '$(hostname)']"

TEST_NAME="${TEST_NAME_BASE}-200-curl-jobs-json"
run_ok "${TEST_NAME}" \
    curl "${TEST_CYLC_WS_URL}/taskjobs/${USER}/${ESC_SUITE_NAME}?form=json"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('logo',), 'cylc-logo.png']" \
    "[('title',), 'Cylc Review']" \
    "[('host',), '$(hostname)']"
#-------------------------------------------------------------------------------
# Tidy up - note suite trivial so stops early on by itself
purge_suite "${SUITE_NAME}"
cylc_ws_kill
exit
