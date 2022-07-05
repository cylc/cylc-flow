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
# Test remote job logs retrieval, requires compatible version of cylc on remote
# job host.
export REQUIRE_PLATFORM='loc:remote'
. "$(dirname "$0")/test_header"
set_test_number 4
OPT_SET=
create_test_global_config "" "
    [platforms]
        [[${CYLC_TEST_PLATFORM}]]
            retrieve job logs = True
            retrieve job logs retry delays = PT5S
"
OPT_SET='-s GLOBALCFG=True'

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate ${OPT_SET} \
    -s "PLATFORM='${CYLC_TEST_PLATFORM}'" "${WORKFLOW_NAME}"
# shellcheck disable=SC2086
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach ${OPT_SET} \
       -s "PLATFORM='${CYLC_TEST_PLATFORM}'" "${WORKFLOW_NAME}"

sed "/'job-logs-retrieve'/!d" \
    "${WORKFLOW_RUN_DIR}/log/job/1/t1/"{01,02,03}"/job-activity.log" \
    >'edited-activities.log'
cmp_ok 'edited-activities.log' <<'__LOG__'
[(('job-logs-retrieve', 'retry'), 1) ret_code] 0
[(('job-logs-retrieve', 'retry'), 2) ret_code] 0
[(('job-logs-retrieve', 'succeeded'), 3) ret_code] 0
__LOG__

grep -F 'will run after' "${WORKFLOW_RUN_DIR}/log/scheduler/log" \
    | cut -d' ' -f 4-12 | sort >"edited-log"
cmp_ok 'edited-log' <<'__LOG__'
1/t1/01 handler:job-logs-retrieve for task event:retry will run after PT5S
1/t1/02 handler:job-logs-retrieve for task event:retry will run after PT5S
1/t1/03 handler:job-logs-retrieve for task event:succeeded will run after PT5S
__LOG__

purge
exit
