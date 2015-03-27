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
# Test loadleveler directives
#     This test requires an e.g. [test battery][batch systems][loadleveler]host
#     entry in site/user config in order to run 'loadleveler' tests (same for
#     slurm, pbs, etc), otherwise it will be bypassed.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
# export an environment variable for this - allows a script to be used to 
# select a compute node and have that same host used by the suite.
if [[ "${TEST_NAME_BASE}" == ??-loadleveler* ]]; then
    BATCH_SYS_NAME='loadleveler'
elif [[ "${TEST_NAME_BASE}" == ??-slurm* ]]; then
    BATCH_SYS_NAME='slurm'
elif [[ "${TEST_NAME_BASE}" == ??-pbs* ]]; then
    BATCH_SYS_NAME='pbs'
fi
export CYLC_TEST_BATCH_TASK_HOST=$(cylc get-global-config -i \
    "[test battery][batch systems][$BATCH_SYS_NAME]host")
export CYLC_TEST_BATCH_SITE_DIRECTIVES=$(cylc get-global-config -i \
    "[test battery][batch systems][$BATCH_SYS_NAME][directives]")
if [[ -z "${CYLC_TEST_BATCH_TASK_HOST}" || "${CYLC_TEST_BATCH_TASK_HOST}" == None ]]
then
    skip_all "[directive tests]$BATCH_SYS_NAME host not defined"
fi
# check the host is reachable
if ! ssh -n ${SSH_OPTS} "${CYLC_TEST_BATCH_TASK_HOST}" true 1>/dev/null 2>&1
then
    skip_all "Host "$CYLC_TEST_BATCH_TASK_HOST" unreachable"
fi

set_test_number 2
install_suite "${TEST_NAME_BASE}" "${BATCH_SYS_NAME}"
# copy across passphrase as not all remote hosts will have a shared file system
# the .cylc location is used as registration and run directory won't be the same
ssh ${SSH_OPTS} -n "${CYLC_TEST_BATCH_TASK_HOST}" \
    "mkdir -p '.cylc/${SUITE_NAME}/'"
scp ${SSH_OPTS} "${TEST_DIR}/${SUITE_NAME}/passphrase" \
    "${CYLC_TEST_BATCH_TASK_HOST}:.cylc/${SUITE_NAME}/passphrase"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug "${SUITE_NAME}"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
ssh -n ${SSH_OPTS} "${CYLC_TEST_BATCH_TASK_HOST}" \
    "rm -fr .cylc/${SUITE_NAME} cylc-run/${SUITE_NAME}"
exit
