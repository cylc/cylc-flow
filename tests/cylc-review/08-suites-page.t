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
# Test for "cylc review", suites list, glob, sort and page.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python2 -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 15
#-------------------------------------------------------------------------------
# Initialise multiple suites with same 'suite.rc' file; name [abc] and [1-10]
PREFIX="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}"

# Group '1'
PREFIX_GROUP1="${PREFIX}-1-"
for SUFFIX in 'b' 'a' 'c'; do
    cp "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/suite.rc" .
    # Make one of set [abc] a symlink
    if [[ "${SUFFIX}" == 'a' ]]; then
        mkdir -p "${PREFIX_GROUP1}${SUFFIX}"
        ln -s "${PWD}/${PREFIX_GROUP1}${SUFFIX}" "${HOME}/cylc-run/${PREFIX_GROUP1}${SUFFIX}"
    fi
    cylc register "${PREFIX_GROUP1}${SUFFIX}" "${PWD}"
    cylc run --no-detach --debug "${PREFIX_GROUP1}${SUFFIX}" 2>'/dev/null' \
        || cat "${HOME}/cylc-run/${PREFIX_GROUP1}${SUFFIX}/log/suite/err" >&2
done

# Group '2'
PREFIX_GROUP2="${PREFIX}-2-"
for SUFFIX in $(seq -w 1 10); do
    cp "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/suite.rc" .
    cylc register "${PREFIX_GROUP2}${SUFFIX}" "${PWD}"
    cylc run --no-detach --debug "${PREFIX_GROUP2}${SUFFIX}" 2>'/dev/null' \
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
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP1}c']" \
    "[('entries', 1, 'name'), '${PREFIX_GROUP1}a']" \
    "[('entries', 2, 'name'), '${PREFIX_GROUP1}b']"
#-------------------------------------------------------------------------------
# Data transfer output check for [abc], sort by time_asc
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-time-asc"
ARGS="&names=${PREFIX_GROUP1}*&order=time_asc"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP1}b']" \
    "[('entries', 1, 'name'), '${PREFIX_GROUP1}a']" \
    "[('entries', 2, 'name'), '${PREFIX_GROUP1}c']"
#-------------------------------------------------------------------------------
# Data transfer output check for [abc], sort by name_asc
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-name-asc"
ARGS="&names=${PREFIX_GROUP1}*&order=name_asc"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP1}a']" \
    "[('entries', 1, 'name'), '${PREFIX_GROUP1}b']" \
    "[('entries', 2, 'name'), '${PREFIX_GROUP1}c']"
#-------------------------------------------------------------------------------
# Data transfer output check for [abc], sort by name_desc
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-name-desc"
ARGS="&names=${PREFIX_GROUP1}*&order=name_desc"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP1}c']" \
    "[('entries', 1, 'name'), '${PREFIX_GROUP1}b']" \
    "[('entries', 2, 'name'), '${PREFIX_GROUP1}a']"
#-------------------------------------------------------------------------------
# Data transfer output check for [1-10], page 1
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-2-page-1"
ARGS="&names=${PREFIX_GROUP2}*&per_page=4&page=1"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 1]" \
    "[('per_page',), 4]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP2}10']" \
    "[('entries', 1, 'name'), '${PREFIX_GROUP2}09']" \
    "[('entries', 2, 'name'), '${PREFIX_GROUP2}08']" \
    "[('entries', 3, 'name'), '${PREFIX_GROUP2}07']"
#-------------------------------------------------------------------------------
# Data transfer output check for [1-10], page 2
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-2-page-2"
ARGS="&names=${PREFIX_GROUP2}*&per_page=4&page=2"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 2]" \
    "[('per_page',), 4]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP2}06']" \
    "[('entries', 1, 'name'), '${PREFIX_GROUP2}05']" \
    "[('entries', 2, 'name'), '${PREFIX_GROUP2}04']" \
    "[('entries', 3, 'name'), '${PREFIX_GROUP2}03']"
#-------------------------------------------------------------------------------
# Data transfer output check for [1-10], page 3
TEST_NAME="${TEST_NAME_BASE}-200-curl-suites-2-page-3"
ARGS="&names=${PREFIX_GROUP2}*&per_page=4&page=3"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/suites/${USER}?form=json${ARGS}"
cylc_ws_json_greps "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" \
    "[('page',), 3]" \
    "[('per_page',), 4]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'name'), '${PREFIX_GROUP2}02']" \
    "[('entries', 1, 'name'), '${PREFIX_GROUP2}01']"
#-------------------------------------------------------------------------------
# Tidy up - note suites trivial so stop early on by themselves
rm -fr \
    "${HOME}/cylc-run/${PREFIX_GROUP1}"[abc] \
    "${HOME}/cylc-run/${PREFIX_GROUP2}"?? \
2>'/dev/null'
cylc_ws_kill
exit
