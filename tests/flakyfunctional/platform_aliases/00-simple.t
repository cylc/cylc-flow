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
# Test that a different platform is selected on different tries with the same
# platform Alias.
#
# Because this test can only ever test that all platforms within an alias have
# been used it is theoretically possible for the random selection from Python's
# random.choice to continue selecting the same platform forever, which is the
# same outcome as failure. As a result this test is deliberately slightly flaky:
# It triggers the platform alias task $TASTE_FOR_FLAKINESS times and fails
# when if both platforms have not been selected once after this number of retries.
# If $TASTE_FOR_FLAKINESS = 9 this is equivelent to a 0.039 % chance of a false
# negative if the code is working.

. "$(dirname "$0")/test_header"
require_remote_platform
set_test_number 2

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
LOCAL_HOSTNAME=$(hostname)
create_test_global_config "" "
[platforms]
  [[platform1]]
    hosts = ${LOCAL_HOSTNAME}
  [[platform2]]
    hosts = ${LOCAL_HOSTNAME}

[platform groups]
  [[test_alias]]
    platforms = platform2, platform1
"


run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

# Since this suite is meant to hold we don't want to test whether it runs ok.
cylc run "${SUITE_NAME}"
DBPATH="${SUITE_RUN_DIR}/log/db"
TASTE_FOR_FLAKINESS=9
i=0
while true; do
  ((i=i+1))
  poll_grep "succeeded" "${SUITE_RUN_DIR}/log/job/1/task_with_platform_alias/0${i}/job.out"
  cylc trigger "${SUITE_NAME}" task_with_platform_alias.1
  if [[ $i -gt 1 ]]; then
    dbinfo=$(sqlite3 "${DBPATH}" "SELECT name, platform_name from task_jobs")
    if grep -q 'platform1' <<< "$dbinfo" && grep -q 'platform2' <<< "$dbinfo"; then
      ok "${TEST_NAME_BASE}-all-platforms-used"
      break
    fi
    if [[ $i > "${TASTE_FOR_FLAKINESS}" ]]; then
      if [[ -n "${TEST_VERBOSE:-}" ]]; then
        echo "There is a 1 in 2/2^${TASTE_FOR_FLAKINESS} probability that this is a false-negative" >&2
      fi
      fail "${TEST_NAME_BASE}-all-platforms-used"
      break
    fi
  fi

done

cylc stop "${SUITE_NAME}"
purge_suite_platform "${CYLC_TEST_PLATFORM}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
