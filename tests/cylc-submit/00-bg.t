#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
# Test "cylc submit" a background task.
. $(dirname $0)/test_header

CYLC_TEST_HOST='localhost'
if [[ "${TEST_NAME_BASE}" == *remote* ]]; then
    CONF_KEY='remote host'
    if [[ "${TEST_NAME_BASE}" == *remote-with-shared-fs* ]]; then
        CONF_KEY='remote host with shared fs'
    fi
    HOST="$(cylc get-global-config "--item=[test battery]${CONF_KEY}")"
    if [[ -z "${HOST}" ]]; then
        skip_all "[test battery]${CONF_KEY} not set"
    fi
    CYLC_TEST_HOST="${HOST}"
fi
CYLC_TEST_BATCH_SYS_NAME='background'
CONFIGURED_SYS_NAME=
CYLC_TEST_DIRECTIVES=
if [[ "${TEST_NAME_BASE}" == ??-at* ]]; then
    CYLC_TEST_BATCH_SYS_NAME='at'
elif [[ "${TEST_NAME_BASE}" == ??-loadleveler* ]]; then
    CONFIGURED_SYS_NAME='loadleveler'
elif [[ "${TEST_NAME_BASE}" == ??-slurm* ]]; then
    CONFIGURED_SYS_NAME='slurm'
elif [[ "${TEST_NAME_BASE}" == ??-pbs* ]]; then
    CONFIGURED_SYS_NAME='pbs'
elif [[ "${TEST_NAME_BASE}" == ??-lsf* ]]; then
    CONFIGURED_SYS_NAME='lsf'
fi
if [[ -n $CONFIGURED_SYS_NAME ]]; then
    ITEM_KEY="[test battery][batch systems][$CONFIGURED_SYS_NAME]host"
    CYLC_TEST_HOST="$(cylc get-global-config "--item=${ITEM_KEY}")"
    if [[ -z "${CYLC_TEST_HOST}" ]]; then
        skip_all "${ITEM_KEY} not set"
    fi
    ITEM_KEY="[test battery][batch systems][$CONFIGURED_SYS_NAME][directives]"
    CYLC_TEST_DIRECTIVES="$(cylc get-global-config "--item=${ITEM_KEY}")"
    CYLC_TEST_BATCH_SYS_NAME=$CONFIGURED_SYS_NAME
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
        use login shell = False
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
    "--set=CYLC_TEST_BATCH_SYS_NAME=${CYLC_TEST_BATCH_SYS_NAME}" \
    "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}" \
    cylc submit \
    "--set=CYLC_TEST_HOST=${CYLC_TEST_HOST}" \
    "--set=CYLC_TEST_BATCH_SYS_NAME=${CYLC_TEST_BATCH_SYS_NAME}" \
    "${SUITE_NAME}" 'foo.1'
SUITE_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
if [[ -n "${SSH}" ]]; then
    SUITE_DIR="${SUITE_DIR#"${HOME}/"}"
    ST_FILE="${SUITE_DIR}/log/job/1/foo/01/job.status"
    poll ! $SSH "grep -q 'CYLC_BATCH_SYS_JOB_ID=' \"${ST_FILE}\"" 2>/dev/null
    JOB_ID=$($SSH "cat \"${ST_FILE}\"" \
        | awk -F= '$1 == "CYLC_BATCH_SYS_JOB_ID" {print $2}')
else
    ST_FILE="${SUITE_DIR}/log/job/1/foo/01/job.status"
    poll ! grep -q 'CYLC_BATCH_SYS_JOB_ID=' "${ST_FILE}" 2>/dev/null
    JOB_ID=$(awk -F= '$1 == "CYLC_BATCH_SYS_JOB_ID" {print $2}' "${ST_FILE}")
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
