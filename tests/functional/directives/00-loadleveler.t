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
# Test loadleveler directives
#     This test requires an e.g. [test battery][batch systems][loadleveler]host
#     entry in site/user config in order to run 'loadleveler' tests (same for
#     slurm, pbs, etc), otherwise it will be bypassed.
# TODO Check this test on a dockerized system or VM.
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
# export an environment variable for this - allows a script to be used to 
# select a compute node and have that same host used by the suite.
BATCH_SYS_NAME="${TEST_NAME_BASE##??-}"
RC_PREF="[test battery][batch systems][${BATCH_SYS_NAME}]"
CYLC_TEST_BATCH_TASK_HOST=$( \
    cylc get-global-config -i "${RC_PREF}host" 2>'/dev/null')
CYLC_TEST_BATCH_SITE_DIRECTIVES=$( \
    cylc get-global-config -i "${RC_PREF}[directives]" 2>'/dev/null')
if [[ -z "${CYLC_TEST_BATCH_TASK_HOST}" || "${CYLC_TEST_BATCH_TASK_HOST}" == None ]]
then
    skip_all "\"[test battery][batch systems][$BATCH_SYS_NAME]host\" not defined"
fi
export CYLC_TEST_BATCH_TASK_HOST CYLC_TEST_BATCH_SITE_DIRECTIVES

set_test_number 2
reftest "${TEST_NAME_BASE}" "${BATCH_SYS_NAME}"
purge_suite_remote "${CYLC_TEST_BATCH_TASK_HOST}" "${SUITE_NAME}"
exit
