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
# Test for "rose bush", suites list, glob, sort and page.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

tests 15

ROSE_CONF_PATH= rose_ws_init 'rose' 'bush'
if [[ -z "${TEST_ROSE_WS_PORT}" ]]; then
    exit 1
fi

cat >'suite.rc' <<'__SUITE_RC__'
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

#-------------------------------------------------------------------------------
# Run a few cylc suites
export CYLC_CONF_PATH=
mkdir -p "${HOME}/cylc-run"
SUITE_NAME_1_PREFIX="rtb-rose-bush-08-$(uuidgen)-"
for SUFFIX in 'b' 'a' 'c'; do
    SUITE_NAME="${SUITE_NAME_1_PREFIX}${SUFFIX}"
    SUITE_DIR="${HOME}/cylc-run/${SUITE_NAME}"
    # Make one of these a symlink
    if [[ "${SUFFIX}" == 'a' ]]; then
        mkdir "${SUITE_NAME}"
        ln -s "${PWD}/${SUITE_NAME}" "${SUITE_DIR}"
    else
        mkdir -p "${SUITE_DIR}"
    fi
    cp -p 'suite.rc' "${SUITE_DIR}/suite.rc"
    cylc register "${SUITE_NAME}" "${SUITE_DIR}"
    cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null' \
        || cat "${SUITE_DIR}/log/suite/err" >&2
done

# Run another set of suites, for glob and paging tests
SUITE_NAME_2_PREFIX="rtb-rose-bush-08-$(uuidgen)-"
for SUFFIX in $(seq -w 1 10); do
    SUITE_NAME="${SUITE_NAME_2_PREFIX}${SUFFIX}"
    SUITE_DIR="${HOME}/cylc-run/${SUITE_NAME}"
    mkdir -p "${SUITE_DIR}"
    cp -p 'suite.rc' "${SUITE_DIR}/suite.rc"
    cylc register "${SUITE_NAME}" "${SUITE_DIR}"
    cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null' \
        || cat "${SUITE_DIR}/log/suite/err" >&2
done
#-------------------------------------------------------------------------------
# Batch 1, sort by time_desc
TEST_KEY="${TEST_KEY_BASE}-200-curl-suites"
ARGS="&names=${SUITE_NAME_1_PREFIX}*"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/suites/${USER}?form=json${ARGS}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${SUITE_NAME_1_PREFIX}c']" \
    "[('entries', 1, 'name'), '${SUITE_NAME_1_PREFIX}a']" \
    "[('entries', 2, 'name'), '${SUITE_NAME_1_PREFIX}b']"
#-------------------------------------------------------------------------------
# Batch 1, sort by time_asc
TEST_KEY="${TEST_KEY_BASE}-200-curl-suites-time-asc"
ARGS="&names=${SUITE_NAME_1_PREFIX}*&order=time_asc"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/suites/${USER}?form=json${ARGS}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${SUITE_NAME_1_PREFIX}b']" \
    "[('entries', 1, 'name'), '${SUITE_NAME_1_PREFIX}a']" \
    "[('entries', 2, 'name'), '${SUITE_NAME_1_PREFIX}c']"
#-------------------------------------------------------------------------------
# Batch 1, sort by name_asc
TEST_KEY="${TEST_KEY_BASE}-200-curl-suites-name-asc"
ARGS="&names=${SUITE_NAME_1_PREFIX}*&order=name_asc"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/suites/${USER}?form=json${ARGS}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${SUITE_NAME_1_PREFIX}a']" \
    "[('entries', 1, 'name'), '${SUITE_NAME_1_PREFIX}b']" \
    "[('entries', 2, 'name'), '${SUITE_NAME_1_PREFIX}c']"
#-------------------------------------------------------------------------------
# Batch 1, sort by name_desc
TEST_KEY="${TEST_KEY_BASE}-200-curl-suites-name-desc"
ARGS="&names=${SUITE_NAME_1_PREFIX}*&order=name_desc"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/suites/${USER}?form=json${ARGS}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('page',), 1]" \
    "[('per_page',), 100]" \
    "[('of_n_entries',), 3]" \
    "[('entries', 0, 'name'), '${SUITE_NAME_1_PREFIX}c']" \
    "[('entries', 1, 'name'), '${SUITE_NAME_1_PREFIX}b']" \
    "[('entries', 2, 'name'), '${SUITE_NAME_1_PREFIX}a']"
#-------------------------------------------------------------------------------
# Batch 2, page 1
TEST_KEY="${TEST_KEY_BASE}-200-curl-suites-2-page-1"
ARGS="&names=${SUITE_NAME_2_PREFIX}*&per_page=4&page=1"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/suites/${USER}?form=json${ARGS}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('page',), 1]" \
    "[('per_page',), 4]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'name'), '${SUITE_NAME_2_PREFIX}10']" \
    "[('entries', 1, 'name'), '${SUITE_NAME_2_PREFIX}09']" \
    "[('entries', 2, 'name'), '${SUITE_NAME_2_PREFIX}08']" \
    "[('entries', 3, 'name'), '${SUITE_NAME_2_PREFIX}07']"
#-------------------------------------------------------------------------------
# Batch 2, page 2
TEST_KEY="${TEST_KEY_BASE}-200-curl-suites-2-page-2"
ARGS="&names=${SUITE_NAME_2_PREFIX}*&per_page=4&page=2"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/suites/${USER}?form=json${ARGS}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('page',), 2]" \
    "[('per_page',), 4]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'name'), '${SUITE_NAME_2_PREFIX}06']" \
    "[('entries', 1, 'name'), '${SUITE_NAME_2_PREFIX}05']" \
    "[('entries', 2, 'name'), '${SUITE_NAME_2_PREFIX}04']" \
    "[('entries', 3, 'name'), '${SUITE_NAME_2_PREFIX}03']"
#-------------------------------------------------------------------------------
# Batch 2, page 3
TEST_KEY="${TEST_KEY_BASE}-200-curl-suites-2-page-3"
ARGS="&names=${SUITE_NAME_2_PREFIX}*&per_page=4&page=3"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/suites/${USER}?form=json${ARGS}"
rose_ws_json_greps "${TEST_KEY}.out" "${TEST_KEY}.out" \
    "[('page',), 3]" \
    "[('per_page',), 4]" \
    "[('of_n_entries',), 10]" \
    "[('entries', 0, 'name'), '${SUITE_NAME_2_PREFIX}02']" \
    "[('entries', 1, 'name'), '${SUITE_NAME_2_PREFIX}01']"
#-------------------------------------------------------------------------------
# Tidy up
rose_ws_kill
rm -fr \
    "${HOME}/cylc-run/${SUITE_NAME_1_PREFIX}"[abc] \
    "${HOME}/cylc-run/${SUITE_NAME_2_PREFIX}"?? \
    2>'/dev/null'
exit 0
