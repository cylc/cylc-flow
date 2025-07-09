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
# Test "log/config/*-<mode>.cylc" files that are generated on workflow start up.
. "$(dirname "$0")/test_header"
set_test_number 10

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
#!Jinja2
[meta]
    title = a workflow that logs run, reload, and restart configs
    description = the weather is {{WEATHER | default("bad")}}
[scheduler]
    [[events]]
        abort on stall timeout = True
        stall timeout = PT0S
        restart timeout = PT0S  # shut down when restarted with empty pool
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

# Check for 4 generated *.cylc files
LOGD="${RUN_DIR}/${WORKFLOW_NAME}/log/config"
# shellcheck disable=SC2012
ls "${LOGD}" | sort >'ls.out'
cmp_ok 'ls.out' <<'__OUT__'
01-start-01.cylc
02-reload-01.cylc
03-restart-02.cylc
flow-processed.cylc
__OUT__

LOGD="${RUN_DIR}/${WORKFLOW_NAME}/log/config"
START_CONFIG="$(ls "${LOGD}/"*-start*.cylc)"
REL_CONFIG="$(ls "${LOGD}/"*-reload*.cylc)"
RES_CONFIG="$(ls "${LOGD}/"*-restart*.cylc)"
mkdir start_config
mkdir res_config
cp "$START_CONFIG" start_config/flow.cylc
cp "$RES_CONFIG" res_config/flow.cylc
# The generated *-start*.cylc and *-reload*.cylc should be identical
# The generated *.cylc files should validate
cmp_ok "${START_CONFIG}" "${REL_CONFIG}"
run_ok "${TEST_NAME_BASE}-validate-start-config" cylc validate ./start_config
run_ok "${TEST_NAME_BASE}-validate-restart-config" cylc validate ./res_config
rm -rf start_config res_config

diff -u "${START_CONFIG}" "${RES_CONFIG}" >'diff.out'
contains_ok 'diff.out' <<'__DIFF__'
-    description = the weather is bad
+    description = the weather is good
__DIFF__

# Ensure that the start config is sparse.
grep_fail "\[\[mail\]\]" "${START_CONFIG}"

purge
exit
