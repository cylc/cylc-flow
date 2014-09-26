#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test "cylc submit" a background task.
. $(dirname $0)/test_header

CYLC_TEST_HOST='localhost'
if [[ "${TEST_NAME_BASE}" == *remote* ]]; then
    CONF_KEY='remote host'
    if [[ "${TEST_NAME_BASE}" == *remote-with-shared-fs* ]]; then
        CONF_KEY='remote host with shared fs'
    fi
    if ! HOST="$(cylc get-global-config "--item=[test battery]${CONF_KEY}")"
    then
        skip_all "[test battery]${CONF_KEY} not set"
    fi
    CYLC_TEST_HOST="${HOST}"
fi
CYLC_TEST_JOB_SUBMIT_METHOD='background'
CYLC_TEST_DIRECTIVES=
if [[ "${TEST_NAME_BASE}" == ??-at* ]]; then
    CYLC_TEST_JOB_SUBMIT_METHOD='at'
elif [[ "${TEST_NAME_BASE}" == ??-loadleveler* ]]; then
    CYLC_TEST_JOB_SUBMIT_METHOD='loadleveler'
    ITEM_KEY='[test battery][directives]loadleveler host'
    CYLC_TEST_HOST="$(cylc get-global-config "--item=${ITEM_KEY}")"
    if [[ -z "${CYLC_TEST_HOST}" ]]; then
        skip_all "${ITEM_KEY} not set"
    fi
    ITEM_KEY='[test battery][directives]loadleveler directives'
    CYLC_TEST_DIRECTIVES="$(cylc get-global-config "--item=${ITEM_KEY}")"
fi
export CYLC_CONF_DIR=
SSH=
if [[ "${CYLC_TEST_HOST}" != 'localhost' ]]; then
    SSH="ssh -oBatchMode=yes -oConnectTimeout=5 ${CYLC_TEST_HOST}"
    ssh_install_cylc "${CYLC_TEST_HOST}"
    mkdir -p 'conf'
    cat >"conf/global.rc" <<__GLOBAL_RC__
[hosts]
    [[${CYLC_TEST_HOST}]]
        cylc executable = ${TEST_RHOST_CYLC_DIR#*:}/bin/cylc
__GLOBAL_RC__
    export CYLC_CONF_DIR="${PWD}/conf"
fi
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate \
    "--set=CYLC_TEST_HOST=${CYLC_TEST_HOST}" \
    "--set=CYLC_TEST_JOB_SUBMIT_METHOD=${CYLC_TEST_JOB_SUBMIT_METHOD}" \
    "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}" \
    cylc submit \
    "--set=CYLC_TEST_HOST=${CYLC_TEST_HOST}" \
    "--set=CYLC_TEST_JOB_SUBMIT_METHOD=${CYLC_TEST_JOB_SUBMIT_METHOD}" \
    "${SUITE_NAME}" 'foo.1'
SUITE_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
if [[ -n "${SSH}" ]]; then
    SUITE_DIR="${SUITE_DIR#"${HOME}/"}"
    ST_FILE="${SUITE_DIR}/log/job/1/foo/01/job.status"
    poll ! $SSH "grep -q 'CYLC_JOB_SUBMIT_METHOD_ID=' \"${ST_FILE}\"" 2>/dev/null
    JOB_ID=$($SSH "cat \"${ST_FILE}\"" \
        | awk -F= '$1 == "CYLC_JOB_SUBMIT_METHOD_ID" {print $2}')
else
    ST_FILE="${SUITE_DIR}/log/job/1/foo/01/job.status"
    poll ! grep -q 'CYLC_JOB_SUBMIT_METHOD_ID=' "${ST_FILE}" 2>/dev/null
    JOB_ID=$(awk -F= '$1 == "CYLC_JOB_SUBMIT_METHOD_ID" {print $2}' "${ST_FILE}")
fi
cmp_ok "${TEST_NAME_BASE}.stdout" <<__OUT__
Job ID: ${JOB_ID}
__OUT__
cmp_ok "${TEST_NAME_BASE}.stderr" <'/dev/null'
#-------------------------------------------------------------------------------
if [[ -n "${SSH}" ]]; then
    poll ! $SSH "grep -q 'CYLC_JOB_EXIT=' \"${ST_FILE}\"" 2>/dev/null
    $SSH "rm -r ${SUITE_DIR}" 2>/dev/null
else
    poll ! grep -q 'CYLC_JOB_EXIT=' "${ST_FILE}" 2>/dev/null
fi
purge_suite "${SUITE_NAME}"
exit
