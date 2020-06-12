#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
# Test "cylc submit" a background task.
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"

CYLC_TEST_HOST='localhost'
if [[ "${TEST_NAME_BASE}" == *remote* ]]; then
    CONF_KEY='remote host'
    if [[ "${TEST_NAME_BASE}" == *remote-with-shared-fs* ]]; then
        CONF_KEY='remote host with shared fs'
    fi
    RC_ITEM="[test battery]${CONF_KEY}"
    HOST="$(cylc get-global-config "--item=${RC_ITEM}" 2>'/dev/null')"
    if [[ -z "${HOST}" ]]; then
        skip_all "\"[test battery]${CONF_KEY}\" not defined"
    fi
    CYLC_TEST_HOST="${HOST}"
fi
CONFIGURED_SYS_NAME=
CYLC_TEST_DIRECTIVES=
CONFIGURED_SYS_NAME="${TEST_NAME_BASE##??-}"
if [[ "${CONFIGURED_SYS_NAME}" == 'bg' || "${CONFIGURED_SYS_NAME}" == *-bg ]]
then
    CONFIGURED_SYS_NAME=
    CYLC_TEST_BATCH_SYS_NAME='background'
elif [[ "${CONFIGURED_SYS_NAME}" == 'at' || "${CONFIGURED_SYS_NAME}" == *-at ]]
then
    CONFIGURED_SYS_NAME=
    CYLC_TEST_BATCH_SYS_NAME='at'
    skip_darwin 'atrun hard to configure on Mac OS'
fi
if [[ -n "${CONFIGURED_SYS_NAME}" ]]; then
    ITEM_KEY="[test battery][batch systems][$CONFIGURED_SYS_NAME]host"
    CYLC_TEST_HOST="$( \
        cylc get-global-config "--item=${ITEM_KEY}" 2>'/dev/null')"
    if [[ -z "${CYLC_TEST_HOST}" ]]; then
        skip_all "\"${ITEM_KEY}\" not set"
    fi
    ITEM_KEY="[test battery][batch systems][$CONFIGURED_SYS_NAME][directives]"
    CYLC_TEST_DIRECTIVES="$( \
        cylc get-global-config "--item=${ITEM_KEY}" 2>'/dev/null')"
    export CYLC_TEST_DIRECTIVES
    CYLC_TEST_BATCH_SYS_NAME=$CONFIGURED_SYS_NAME
fi
SSH=
if [[ "${CYLC_TEST_HOST}" != 'localhost' ]]; then
    SSH="ssh -oBatchMode=yes -oConnectTimeout=5 ${CYLC_TEST_HOST}"
    ssh_install_cylc "${CYLC_TEST_HOST}"
    create_test_globalrc "" "
[hosts]
    [[${CYLC_TEST_HOST}]]
        cylc executable = ${TEST_RHOST_CYLC_DIR#*:}/bin/cylc
        use login shell = False"
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
    # shellcheck disable=SC2086
    poll $SSH "grep -q 'CYLC_BATCH_SYS_JOB_ID=' \"${ST_FILE}\"" 2>'/dev/null'
    # shellcheck disable=SC2086
    JOB_ID=$($SSH "cat \"${ST_FILE}\"" \
        | awk -F= '$1 == "CYLC_BATCH_SYS_JOB_ID" {print $2}')
else
    ST_FILE="${SUITE_DIR}/log/job/1/foo/01/job.status"
    poll_grep 'CYLC_BATCH_SYS_JOB_ID=' "${ST_FILE}"
    JOB_ID=$(awk -F= '$1 == "CYLC_BATCH_SYS_JOB_ID" {print $2}' "${ST_FILE}")
fi
contains_ok "${TEST_NAME_BASE}.stdout" <<<"[foo.1] Job ID: ${JOB_ID}"
cmp_ok "${TEST_NAME_BASE}.stderr" <'/dev/null'
#-------------------------------------------------------------------------------
if [[ -n "${SSH}" ]]; then
    # shellcheck disable=SC2086
    poll $SSH "grep -q 'CYLC_JOB_INIT_TIME=' \"${ST_FILE}\"" 2>'/dev/null'
    # shellcheck disable=SC2086
    poll $SSH "grep -q 'CYLC_JOB_EXIT=' \"${ST_FILE}\"" 2>'/dev/null'
    purge_suite_remote "${CYLC_TEST_HOST}" "${SUITE_NAME}"
else
    poll_grep 'CYLC_JOB_INIT_TIME=' "${ST_FILE}"
    poll_grep 'CYLC_JOB_EXIT=' "${ST_FILE}"
fi
purge_suite "${SUITE_NAME}"
exit
