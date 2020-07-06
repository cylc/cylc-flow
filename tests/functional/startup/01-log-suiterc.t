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
# Test "log/suiterc/*-<mode>.rc" files that are generated on suite start up.
. "$(dirname "$0")/test_header"
set_test_number 9

init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
#!Jinja2
[meta]
    title = a suite that logs run, reload, and restart configs
    description = the weather is {{WEATHER | default("bad")}}
[cylc]
    [[events]]
        abort on stalled = True
[scheduling]
    [[graph]]
        R1 = reloader => whatever
[runtime]
    [[reloader]]
        script = cylc reload "${CYLC_SUITE_NAME}"
    [[whatever]]
        script = true
__SUITERC__

run_ok "${TEST_NAME_BASE}-val-1" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-val-2" \
    cylc validate --set 'WEATHER=good' "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" cylc run --no-detach "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-restart" \
    cylc restart --set 'WEATHER=good' --no-detach "${SUITE_NAME}"

# Check for 3 generated *.rc files
LOGD="$RUN_DIR/${SUITE_NAME}/log/suiterc"
# shellcheck disable=SC2012
ls "${LOGD}" | sed -e 's/.*-//g' | sort >'ls.out'
cmp_ok 'ls.out' <<'__OUT__'
reload.rc
restart.rc
run.rc
__OUT__

LOGD="$RUN_DIR/${SUITE_NAME}/log/suiterc"
RUN_RC="$(ls "${LOGD}/"*-run.rc)"
REL_RC="$(ls "${LOGD}/"*-reload.rc)"
RES_RC="$(ls "${LOGD}/"*-restart.rc)"
# The generated *-run.rc and *-reload.rc should be identical
# The generated *.rc files should validate
cmp_ok "${RUN_RC}" "${REL_RC}"
run_ok "${TEST_NAME_BASE}-validate-run-rc" cylc validate "${RUN_RC}"
run_ok "${TEST_NAME_BASE}-validate-restart-rc" cylc validate "${RES_RC}"

diff -u "${RUN_RC}" "${RES_RC}" >'diff.out'
contains_ok 'diff.out' <<'__DIFF__'
-    description = the weather is bad
+    description = the weather is good
__DIFF__

purge_suite "${SUITE_NAME}"
exit
