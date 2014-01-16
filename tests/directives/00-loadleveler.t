#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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
#C: Test loadleveler directives
#C:     This test requires a [directive-tests]loadleveler-host entry in 
#C:     site/user config in order to run, otherwise it will be bypassed
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
# export an environment variable for this - allows a script to be used to 
# select a compute node and have that same host used by the suite.
export CYLC_LL_TEST_TASK_HOST=$(cylc get-global-config -i '[test battery][directives]loadleveler host')
export CYLC_LL_TEST_SITE_DIRECTIVES=$(cylc get-global-config -i '[test battery][directives][loadleveler directives]')
if [[ -n $CYLC_LL_TEST_TASK_HOST && $CYLC_LL_TEST_TASK_HOST != None ]]; then
    # check the host is reachable
    if ping -c 1 $CYLC_LL_TEST_TASK_HOST 1>/dev/null 2>&1; then
        install_suite $TEST_NAME_BASE loadleveler
#-------------------------------------------------------------------------------
# copy across passphrase as not all remote hosts will have a shared file system
# the .cylc location is used as registration and run directory won't be the same
        ssh $CYLC_LL_TEST_TASK_HOST mkdir -p .cylc/$SUITE_NAME/
        scp $TEST_DIR/$SUITE_NAME/passphrase $CYLC_LL_TEST_TASK_HOST:.cylc/$SUITE_NAME/passphrase
#-------------------------------------------------------------------------------
        TEST_NAME=$TEST_NAME_BASE-validate
        run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
        TEST_NAME=$TEST_NAME_BASE-run
        suite_run_ok $TEST_NAME cylc run --reference-test --debug $SUITE_NAME
#-------------------------------------------------------------------------------
        purge_suite $SUITE_NAME
        if [[ -n $SUITE_NAME ]]; then
            ssh $CYLC_LL_TEST_TASK_HOST rm -rf .cylc/$SUITE_NAME
        fi
    else
        skip 2 "Host "$CYLC_LL_TEST_TASK_HOST" unreachable"
    fi
else
    skip 2 '[directive tests]loadleveler host not defined'
fi
unset CYLC_LL_TEST_TASK_HOST

