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
# Test "log/flow-config/*-<mode>.cylc" files that are generated on workflow start up.
. "$(dirname "$0")/test_header"
set_test_number 9

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
#!Jinja2
[meta]
    title = a workflow that logs run, reload, and restart configs
    description = the weather is {{WEATHER | default("bad")}}
[scheduler]
    [[events]]
        abort on stall timeout = True
        stall timeout = PT0S
[scheduling]
    [[graph]]
        R1 = reloader => whatever
[runtime]
    [[reloader]]
        script = cylc reload "${CYLC_WORKFLOW_ID}"
    [[whatever]]
        script = true
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-val-1" cylc validate "${WORKFLOW_NAME}"
run_ok "${TEST_NAME_BASE}-val-2" \
    cylc validate --set 'WEATHER="good"' "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-restart" \
    cylc play --set 'WEATHER="good"' --no-detach "${WORKFLOW_NAME}"

# Check for 3 generated *.cylc files
LOGD="${RUN_DIR}/${WORKFLOW_NAME}/log/flow-config"
# shellcheck disable=SC2012
ls "${LOGD}" | sed -e 's/.*-//g' | sort >'ls.out'
cmp_ok 'ls.out' <<'__OUT__'
processed.cylc
reload.cylc
restart.cylc
start.cylc
__OUT__

LOGD="${RUN_DIR}/${WORKFLOW_NAME}/log/flow-config"
RUN_CONFIG="$(ls "${LOGD}/"*-start.cylc)"
REL_CONFIG="$(ls "${LOGD}/"*-reload.cylc)"
RES_CONFIG="$(ls "${LOGD}/"*-restart.cylc)"
# The generated *-run.cylc and *-reload.cylc should be identical
# The generated *.cylc files should validate
cmp_ok "${RUN_CONFIG}" "${REL_CONFIG}"
run_ok "${TEST_NAME_BASE}-validate-start-config" cylc validate "${RUN_CONFIG}"
run_ok "${TEST_NAME_BASE}-validate-restart-config" cylc validate "${RES_CONFIG}"

diff -u "${RUN_CONFIG}" "${RES_CONFIG}" >'diff.out'
contains_ok 'diff.out' <<'__DIFF__'
-    description = the weather is bad
+    description = the weather is good
__DIFF__

purge
exit
