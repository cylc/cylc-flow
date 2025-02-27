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
# Test "cylc cat-log" with custom out/err tailers
export REQUIRE_PLATFORM='loc:remote runner:background fs:indep comms:tcp'
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 12
#-------------------------------------------------------------------------------
# run the workflow
TEST_NAME="${TEST_NAME_BASE}-validate"
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play -N "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
# change the platform the task ran on to the remote platform
sqlite3 "${HOME}/cylc-run/${WORKFLOW_NAME}/log/db" "
  UPDATE
    task_jobs
  SET
    platform_name = '${CYLC_TEST_PLATFORM}',
    run_status = null
  WHERE
    name = 'foo'
    AND cycle = '1'
;"
#-------------------------------------------------------------------------------
# test cylc cat-log --mode=list-dir will not list job.out / err
# (no tailer / viewer configured)
create_test_global_config "" "
[platforms]
   [[$CYLC_TEST_PLATFORM]]
      out tailer =
      err tailer =
      out viewer =
      err viewer =
  "
TEST_NAME="${TEST_NAME_BASE}-list-dir-no-tailers"
# NOTE: command will fail due to missing remote directory (this tests remote
# error code is preserved)
run_fail "${TEST_NAME}" cylc cat-log "${WORKFLOW_NAME}//1/foo" -m 'list-dir'
# the job.out and job.err filees
grep_fail "job.out" "${TEST_NAME}.stdout"
grep_fail "job.err" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
# test cylc cat-log --mode=list-dir lists the tailed files
# (both tailer and viewer configured)
create_test_global_config "" "
[platforms]
   [[$CYLC_TEST_PLATFORM]]
      out tailer = echo OUT
      err tailer = echo ERR
      out viewer = echo OUT
      err viewer = echo ERR
  "
# test cylc cat-log --mode=list-dir lists the tailed files
TEST_NAME="${TEST_NAME_BASE}-list-dir-with-tailers"
# NOTE: command will fail due to missing remote directory (this tests remote
# error code is preserved)
run_fail "${TEST_NAME}" cylc cat-log "${WORKFLOW_NAME}//1/foo" -m 'list-dir'
# the job.out and job.err filees
grep_ok "job.out" "${TEST_NAME}.stdout"
grep_ok "job.err" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
# test cylc cat-log runs the custom tailers
TEST_NAME="${TEST_NAME_BASE}-cat-out"
run_ok "${TEST_NAME}" cylc cat-log "${WORKFLOW_NAME}//1/foo" -f o -m t
grep_ok "OUT" "${TEST_NAME}.stdout"
run_ok "${TEST_NAME}" cylc cat-log "${WORKFLOW_NAME}//1/foo" -f e -m t
grep_ok "ERR" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
purge
exit
