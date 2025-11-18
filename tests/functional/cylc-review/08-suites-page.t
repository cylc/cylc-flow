#!/bin/bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
# Test for "cylc review", suites list, glob, sort and page.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
requires_cherrypy

set_test_number 15
#-------------------------------------------------------------------------------
# Initialise multiple suites with same 'suite.rc' file; name [abc] and [1-10]
TOP_LEVEL_TEST_DIR="cylctb-${CYLC_TEST_TIME_INIT}"
PREFIX="${TOP_LEVEL_TEST_DIR}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}"

# Group '1'
PREFIX_GROUP1="${PREFIX}-1-"
for SUFFIX in 'a' 'b'; do
    cylc vip "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}" --no-run-name --no-detach --debug --workflow-name "${PREFIX_GROUP1}${SUFFIX}" 2>'/dev/null' \
        || cat "${HOME}/cylc-run/${PREFIX_GROUP1}${SUFFIX}/log/suite/err" >&2
done

# Group '2'
PREFIX_GROUP2="${PREFIX}-2-"
for SUFFIX in $(seq -w 1 3); do
    cylc vip "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}" --no-run-name --no-detach --debug --workflow-name "${PREFIX_GROUP2}${SUFFIX}" 2>'/dev/null' \
        || cat "${HOME}/cylc-run/${PREFIX_GROUP2}${SUFFIX}/log/suite/err" >&2
done

#-------------------------------------------------------------------------------
# Initialise WSGI application for the cylc review web service
TEST_NAME="${TEST_NAME_BASE}-ws-init"
cylc_ws_init 'cylc' 'review'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi
#-------------------------------------------------------------------------------
# Data transfer output check for [abc], sort by time_desc
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites"
ARGS="&names=${PREFIX_GROUP1}*"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 2]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP1}a']" \
    "[('entries', 1, 'name'), '${PREFIX_GROUP1}b']"
#-------------------------------------------------------------------------------
# Data transfer output check for [abc], sort by time_asc
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-time-asc"
ARGS="&names=${PREFIX_GROUP1}*&order=time_asc"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 2]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP1}b']" \
    "[('entries', 1, 'name'), '${PREFIX_GROUP1}a']"
#-------------------------------------------------------------------------------
# Data transfer output check for [abc], sort by name_asc
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-name-asc"
ARGS="&names=${PREFIX_GROUP1}*&order=name_asc"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 2]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP1}a']" \
    "[('entries', 1, 'name'), '${PREFIX_GROUP1}b']"
#-------------------------------------------------------------------------------
# Data transfer output check for [abc], sort by name_desc
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-name-desc"
ARGS="&names=${PREFIX_GROUP1}*&order=name_desc"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 2]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP1}b']" \
    "[('entries', 1, 'name'), '${PREFIX_GROUP1}a']"
#-------------------------------------------------------------------------------
# Data transfer output check for [1-10], page 1
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-2-page-1"
ARGS="&names=${PREFIX_GROUP2}*&per_page=1&page=1"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 1]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP2}1']"
#-------------------------------------------------------------------------------
# Data transfer output check for [1-10], page 2
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-2-page-2"
ARGS="&names=${PREFIX_GROUP2}*&per_page=1&page=2"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 2]" \
    "[('per_page',), 1]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP2}2']"
#-------------------------------------------------------------------------------
# Data transfer output check for [1-10], page 3
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-2-page-3"
ARGS="&names=${PREFIX_GROUP2}*&per_page=1&page=3"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 3]" \
    "[('per_page',), 1]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP2}3']"
#-------------------------------------------------------------------------------
# Tidy up - note suites trivial so stop early on by themselves
rm -fr "${HOME}/cylc-run/${TOP_LEVEL_TEST_DIR}"
cylc_ws_kill
exit
