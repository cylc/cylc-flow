#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
# Test workflow shuts down with reference log, specifically that there is no
# issue in the shutdown method when the --reference-log option is used.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    [[events]]
        abort on inactivity timeout = True
        inactivity timeout = PT3M
[scheduling]
    [[graph]]
        R1 = t1
[runtime]
    [[t1]]
        script = true
__FLOW_CONFIG__
#-------------------------------------------------------------------------------
workflow_run_ok "${TEST_NAME_BASE}-run-reflog" \
    cylc play --debug --no-detach --reference-log "${WORKFLOW_NAME}"

exists_ok "${HOME}/cylc-run/${WORKFLOW_NAME}/reference.log"

delete_db
workflow_run_ok "${TEST_NAME_BASE}-run-reftest" \
    cylc play --debug --no-detach --reference-test "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
purge
exit
