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
# Test "cylc submit" multiple tasks + families.
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"

set_test_number 4

init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[cylc]
    UTC mode = True
    cycle point format = %Y
[scheduling]
    initial cycle point = 2020
    final cycle point = 2021
    [[graph]]
        P1Y = FOO & bar
[runtime]
    [[FOO]]
        script = echo "${CYLC_TASK_ID}"
    [[FOO1, FOO2, FOO3]]
        inherit = FOO
    [[food]]
        inherit = FOO1
    [[fool]]
        inherit = FOO2
    [[foot]]
        inherit = FOO3
    [[bar]]
        script = echo "${CYLC_TASK_ID}"
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}" cylc submit "${SUITE_NAME}" 'FOO.2020' 'bar.2021'
for TASK_ID in 'food.2020' 'fool.2020' 'foot.2020' 'bar.2021'; do
    POINT="${TASK_ID#*.}"
    NAME="${TASK_ID%.*}"
    ST_FILE="${SUITE_RUN_DIR}/log/job/${POINT}/${NAME}/01/job.status"
    JOB_ID="$(awk -F= '$1 == "CYLC_BATCH_SYS_JOB_ID" {print $2}' "${ST_FILE}")"
    echo "[${TASK_ID}] Job ID: ${JOB_ID}"
    poll_pid_done "${JOB_ID}"
done >'expected.out'
contains_ok "${TEST_NAME_BASE}.stdout" 'expected.out'
cmp_ok "${TEST_NAME_BASE}.stderr" <'/dev/null'

purge_suite "${SUITE_NAME}"
exit

