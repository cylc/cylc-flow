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
# Test restarting a simple suite using loadleveler with a submit-failed task
#     This test requires a specific host [test battery] entry in 
#     site/user config in order to run, otherwise it will be bypassed
#-------------------------------------------------------------------------------
TEST_BASE_PATH=$(cd $(dirname $0) && pwd)/03-retrying.t
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
export TEST_DIR
# export an environment variable for this - allows a script to be used to 
# select a compute node and have that same host used by the suite.
if [[ "${TEST_NAME_BASE}" == ??-*-loadleveler* ]]; then
    BATCH_SYS_NAME='loadleveler'
elif [[ "${TEST_NAME_BASE}" == ??-*-slurm* ]]; then
    BATCH_SYS_NAME='slurm'
elif [[ "${TEST_NAME_BASE}" == ??-*-pbs* ]]; then
    BATCH_SYS_NAME='pbs'
fi
export CYLC_TEST_BATCH_TASK_HOST=$(cylc get-global-config -i \
    "[test battery][directives]$BATCH_SYS_NAME host")
export CYLC_TEST_BATCH_SITE_DIRECTIVES=$(cylc get-global-config -i \
    "[test battery][directives][$BATCH_SYS_NAME directives]")
if [[ -n $CYLC_TEST_BATCH_TASK_HOST && $CYLC_TEST_BATCH_TASK_HOST != 'None' ]]
then
    # check the host is reachable
    if ping -c 1 $CYLC_TEST_BATCH_TASK_HOST 1>/dev/null 2>&1; then
        . $TEST_BASE_PATH
    else
        set_test_number 0
    fi
else
    set_test_number 0
fi
unset BATCH_SYS_NAME CYLC_TEST_BATCH_TASK_HOST CYLC_TEST_BATCH_SITE_DIRECTIVES
