#!/usr/bin/env bash
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
# Test remote job logs retrieval, requires compatible version of cylc on remote
# job host.
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
set_test_remote
set_test_number 4
OPT_SET=
if [[ "${TEST_NAME_BASE}" == *-globalcfg ]]; then
    create_test_globalrc "" "
[hosts]
    [[${CYLC_TEST_HOST}]]
        retrieve job logs = True
        retrieve job logs retry delays = PT5S"
    OPT_SET='-s GLOBALCFG=True'
fi

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate ${OPT_SET} -s "HOST=${CYLC_TEST_HOST}" \
       -s "OWNER=${CYLC_TEST_OWNER}" "${SUITE_NAME}"
# shellcheck disable=SC2086
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach ${OPT_SET} \
       -s "HOST=${CYLC_TEST_HOST}" -s "OWNER=${CYLC_TEST_OWNER}" "${SUITE_NAME}"

sed "/'job-logs-retrieve'/!d" \
    "${SUITE_RUN_DIR}/log/job/1/t1/"{01,02,03}"/job-activity.log" \
    >'edited-activities.log'
cmp_ok 'edited-activities.log' <<'__LOG__'
[(('job-logs-retrieve', 'retry'), 1) ret_code] 0
[(('job-logs-retrieve', 'retry'), 2) ret_code] 0
[(('job-logs-retrieve', 'succeeded'), 3) ret_code] 0
__LOG__

grep -F 'will run after' "${SUITE_RUN_DIR}/log/suite/log" \
    | cut -d' ' -f 4-10 | sort >"edited-log"
if [[ "${TEST_NAME_BASE}" == *-globalcfg ]]; then
    cmp_ok 'edited-log' <<'__LOG__'
1/t1/01 ('job-logs-retrieve', 'retry') will run after PT5S
1/t1/02 ('job-logs-retrieve', 'retry') will run after PT5S
1/t1/03 ('job-logs-retrieve', 'succeeded') will run after PT5S
__LOG__
else
    cmp_ok 'edited-log' <'/dev/null'  # P0Y not displayed
fi

purge_suite_remote "${CYLC_TEST_OWNER}@${CYLC_TEST_HOST}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
