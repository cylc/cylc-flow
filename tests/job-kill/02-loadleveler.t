#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
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
# Test killing of jobs submitted to loadleveler, slurm, pbs...
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
if [[ "${TEST_NAME_BASE}" == ??-loadleveler* ]]; then
    BATCH_SYS_NAME='loadleveler'
elif [[ "${TEST_NAME_BASE}" == ??-slurm* ]]; then
    BATCH_SYS_NAME='slurm'
elif [[ "${TEST_NAME_BASE}" == ??-pbs* ]]; then
    BATCH_SYS_NAME='pbs'
fi
export CYLC_TEST_BATCH_TASK_HOST=$(cylc get-global-config -i \
    "[test battery][directives]$BATCH_SYS_NAME host")
export CYLC_TEST_BATCH_SITE_DIRECTIVES=$(cylc get-global-config -i \
    "[test battery][directives][$BATCH_SYS_NAME directives]")
if [[ -n $CYLC_TEST_BATCH_TASK_HOST && $CYLC_TEST_BATCH_TASK_HOST != None ]]; then
    # check the host is reachable
    if ping -c 1 $CYLC_TEST_BATCH_TASK_HOST 1>/dev/null 2>&1; then
        install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
# copy across passphrase as not all remote hosts will have a shared file system
# the .cylc location is used as registration and run directory won't be the same
        SSH='ssh'
        if [[ $CYLC_TEST_BATCH_TASK_HOST != 'localhost' ]]; then
            SSH='ssh -oBatchMode=yes -oConnectTimeout=5'
        fi
        $SSH $CYLC_TEST_BATCH_TASK_HOST mkdir -p .cylc/$SUITE_NAME/
        scp $TEST_DIR/$SUITE_NAME/passphrase $CYLC_TEST_BATCH_TASK_HOST:.cylc/$SUITE_NAME/passphrase
#-------------------------------------------------------------------------------
        TEST_NAME=$TEST_NAME_BASE-validate
        run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
        TEST_NAME=$TEST_NAME_BASE-run
        suite_run_ok $TEST_NAME cylc run --reference-test --debug $SUITE_NAME
#-------------------------------------------------------------------------------
        purge_suite $SUITE_NAME
        if [[ -n $SUITE_NAME ]]; then
            $SSH $CYLC_TEST_BATCH_TASK_HOST rm -rf .cylc/$SUITE_NAME
        fi
    else
        skip 2 "Host "$CYLC_TEST_BATCH_TASK_HOST" unreachable"
    fi
else
    skip 2 "[directive tests]$BATCH_SYS_NAME host not defined"
fi
unset CYLC_TEST_BATCH_TASK_HOST BATCH_SYS_NAME CYLC_TEST_BATCH_SITE_DIRECTIVES
