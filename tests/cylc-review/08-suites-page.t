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
# Test for "cylc review", suites list, glob, sort and page.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 16
#-------------------------------------------------------------------------------
# Set-up multiple suites

# Check the common 'suite.rc' to use is valid
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME

export CYLC_CONF_PATH=
# Initialise multiple suites with same 'suite.rc' file; name [abc] and [1-10]
for SUFFIX in 'b' 'a' 'c' $(seq -w 1 10); do
    SUITE_NAME="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}-${SUFFIX}"
    cylc register "${SUITE_NAME}" "${TEST_DIR}"
    cylc run --no-detach --debug "${SUITE_NAME}"  2>'/dev/null'
    # Make one of set [abc] a symlink
    if [[ "${SUFFIX}" == 'a' ]]; then
        ln -s "${PWD}/${SUITE_NAME}" "${HOME}/cylc-run/${SUITE_NAME}"
    fi
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
ARGS="&names=${SUITE_NAME}*"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${SUITE_NAME}-c']" \
    "[('entries', 1, 'name'), '${SUITE_NAME}-a']" \
    "[('entries', 2, 'name'), '${SUITE_NAME}-b']"
#-------------------------------------------------------------------------------
# Data transfer output check for [abc], sort by time_asc
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-time-asc"
ARGS="&names=${SUITE_NAME}*&order=time_asc"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${SUITE_NAME}-b']" \
    "[('entries', 1, 'name'), '${SUITE_NAME}-a']" \
    "[('entries', 2, 'name'), '${SUITE_NAME}-c']"
#-------------------------------------------------------------------------------
# Data transfer output check for [abc], sort by name_asc
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-name-asc"
ARGS="&names=${SUITE_NAME}*&order=name_asc"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${SUITE_NAME}-a']" \
    "[('entries', 1, 'name'), '${SUITE_NAME}-b']" \
    "[('entries', 2, 'name'), '${SUITE_NAME}-c']"
#-------------------------------------------------------------------------------
# Data transfer output check for [abc], sort by name_desc
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-name-desc"
ARGS="&names=${SUITE_NAME}*&order=name_desc"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${SUITE_NAME}-c']" \
    "[('entries', 1, 'name'), '${SUITE_NAME}-b']" \
    "[('entries', 2, 'name'), '${SUITE_NAME}-a']"
#-------------------------------------------------------------------------------
# Data transfer output check for [1-10], page 1
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-2-page-1"
ARGS="&names=${SUITE_NAME}*&per_page=4&page=1"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 4]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'name'), '${SUITE_NAME}-10']" \
    "[('entries', 1, 'name'), '${SUITE_NAME}-09']" \
    "[('entries', 2, 'name'), '${SUITE_NAME}-08']" \
    "[('entries', 3, 'name'), '${SUITE_NAME}-07']"
#-------------------------------------------------------------------------------
# Data transfer output check for [1-10], page 2
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-2-page-2"
ARGS="&names=${SUITE_NAME}*&per_page=4&page=2"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 2]" \
    "[('per_page',), 4]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'name'), '${SUITE_NAME}-06']" \
    "[('entries', 1, 'name'), '${SUITE_NAME}-05']" \
    "[('entries', 2, 'name'), '${SUITE_NAME}-04']" \
    "[('entries', 3, 'name'), '${SUITE_NAME}-03']"
#-------------------------------------------------------------------------------
# Data transfer output check for [1-10], page 3
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-2-page-3"
ARGS="&names=${SUITE_NAME}*&per_page=4&page=3"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 3]" \
    "[('per_page',), 4]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'name'), '${SUITE_NAME}-02']" \
    "[('entries', 1, 'name'), '${SUITE_NAME}-01']"
#-------------------------------------------------------------------------------
# Tidy up
for SUFFIX in 'a' 'b' 'c' $(seq -w 1 10); do
    SUITE_NAME="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}-${SUFFIX}"
    # Suite trivial so stops early on by itself
    purge_suite "${SUITE_NAME}"
done
cylc_ws_kill
exit
