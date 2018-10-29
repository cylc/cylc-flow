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
# Test for "cylc review", cycles list, paging.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 18
#-------------------------------------------------------------------------------
# Initialise, validate and run a suite for testing with
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
#!Jinja2
[cylc]
    UTC mode = True
[scheduling]
    initial cycle point = 2000
    final cycle point = 2009
    [[dependencies]]
        [[[P1Y]]]
            graph = foo[-P1Y] => foo
[runtime]
    [[foo]]
        script = true
__SUITE_RC__

TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME

cylc run --debug --no-detach $SUITE_NAME 2>'/dev/null'
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
# Data transfer output check for the suite's cycles page, sorted by time_desc
TEST_NAME_PREFIX="${TEST_NAME_BASE}-200-curl-cycles-page-"
for PAGE in {1..4}; do
    TEST_NAME="${TEST_NAME_PREFIX}${PAGE}"
    PAGE_OPT="&page=${PAGE}&per_page=3"
    run_ok "${TEST_NAME}" curl \
        "${TEST_CYLC_WS_URL}/cycles/${USER}/${ESC_SUITE_NAME}?form=json${PAGE_OPT}"
done

# N.B. Extra cycle at the end, due to spawn-held task beyond final cycle point
cylc_ws_json_greps "${TEST_NAME_PREFIX}1.stdout" "${TEST_NAME_PREFIX}1.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 3]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'cycle'), '20090101T0000Z']" \
    "[('entries', 1, 'cycle'), '20080101T0000Z']"
cylc_ws_json_greps "${TEST_NAME_PREFIX}2.stdout" "${TEST_NAME_PREFIX}2.stdout" \
    "[('page',), 2]" \
    "[('per_page',), 3]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'cycle'), '20070101T0000Z']" \
    "[('entries', 1, 'cycle'), '20060101T0000Z']" \
    "[('entries', 2, 'cycle'), '20050101T0000Z']"
cylc_ws_json_greps "${TEST_NAME_PREFIX}3.stdout" "${TEST_NAME_PREFIX}3.stdout" \
    "[('page',), 3]" \
    "[('per_page',), 3]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'cycle'), '20040101T0000Z']" \
    "[('entries', 1, 'cycle'), '20030101T0000Z']" \
    "[('entries', 2, 'cycle'), '20020101T0000Z']"
cylc_ws_json_greps "${TEST_NAME_PREFIX}4.stdout" "${TEST_NAME_PREFIX}4.stdout" \
    "[('page',), 4]" \
    "[('per_page',), 3]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'cycle'), '20010101T0000Z']" \
    "[('entries', 1, 'cycle'), '20000101T0000Z']"
#-------------------------------------------------------------------------------
# Data transfer output check for the suite's cycles page, sorted by time_asc
TEST_NAME_PREFIX="${TEST_NAME_BASE}-200-curl-cycles-asc-page-"
for PAGE in {1..4}; do
    TEST_NAME="${TEST_NAME_PREFIX}${PAGE}"
    PAGE_OPT="&page=${PAGE}&per_page=3&order=time_asc"
    run_ok "${TEST_NAME}" curl \
        "${TEST_CYLC_WS_URL}/cycles/${USER}/${ESC_SUITE_NAME}?form=json${PAGE_OPT}"
done

# N.B. Extra cycle at the end, due to spawn-held task beyond final cycle point
cylc_ws_json_greps "${TEST_NAME_PREFIX}1.stdout" "${TEST_NAME_PREFIX}1.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 3]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'cycle'), '20000101T0000Z']" \
    "[('entries', 1, 'cycle'), '20010101T0000Z']" \
    "[('entries', 2, 'cycle'), '20020101T0000Z']"
cylc_ws_json_greps "${TEST_NAME_PREFIX}2.stdout" "${TEST_NAME_PREFIX}2.stdout" \
    "[('page',), 2]" \
    "[('per_page',), 3]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'cycle'), '20030101T0000Z']" \
    "[('entries', 1, 'cycle'), '20040101T0000Z']" \
    "[('entries', 2, 'cycle'), '20050101T0000Z']"
cylc_ws_json_greps "${TEST_NAME_PREFIX}3.stdout" "${TEST_NAME_PREFIX}3.stdout" \
    "[('page',), 3]" \
    "[('per_page',), 3]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'cycle'), '20060101T0000Z']" \
    "[('entries', 1, 'cycle'), '20070101T0000Z']" \
    "[('entries', 2, 'cycle'), '20080101T0000Z']"
cylc_ws_json_greps "${TEST_NAME_PREFIX}4.stdout" "${TEST_NAME_PREFIX}4.stdout" \
    "[('page',), 4]" \
    "[('per_page',), 3]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'cycle'), '20090101T0000Z']"
#-------------------------------------------------------------------------------
# Tidy up - note suite trivial so stops early on by itself
purge_suite "${SUITE_NAME}"
cylc_ws_kill
exit
