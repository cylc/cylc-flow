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
# Test restarting a simple suite using loadleveler with a running task
#     This test requires a [directive-tests]loadleveler-host entry in 
#     site/user config in order to run, otherwise it will be bypassed
#-------------------------------------------------------------------------------
TEST_BASE_PATH=$(cd $(dirname $0) && pwd)/04-running.t
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
export TEST_DIR
# export an environment variable for this - allows a script to be used to 
# select a compute node and have that same host used by the suite.
export CYLC_LL_TEST_TASK_HOST=$(cylc get-global-config -i '[test battery][directives]loadleveler host')
export CYLC_LL_TEST_SITE_DIRECTIVES=$(cylc get-global-config -i '[test battery][directives][loadleveler directives]')
if [[ -n $CYLC_LL_TEST_TASK_HOST && $CYLC_LL_TEST_TASK_HOST != 'None' ]]; then
    . $TEST_BASE_PATH
else
    skip_all "[test battery][directives]loadleveler host: not defined"
fi
unset CYLC_LL_TEST_TASK_HOST
