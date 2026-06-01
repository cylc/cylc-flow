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
# Test "cylc cat-log" falls back to remote when a specific log file is missing
# locally. This simulates the case where job logs were retrieved but a
# particular file is absent (e.g. due to size limits or retrieval errors).
export REQUIRE_PLATFORM='loc:remote fs:indep'
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 5
create_test_global_config "" "
[platforms]
   [[${CYLC_TEST_PLATFORM}]]
       retrieve job logs = True"
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" \
    cylc play --debug --no-detach \
        -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'" "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
# Confirm job.out is present locally (logs were retrieved).
LOCAL_JOB_DIR=$(cylc cat-log -f a -m d "${WORKFLOW_NAME}//1/a-task")
exists_ok "${LOCAL_JOB_DIR}/job.out"

# Confirm job.err was removed locally by b-task.
exists_fail "${LOCAL_JOB_DIR}/job.err"

# Cat the missing file - should fall back to the remote host and succeed.
TEST_NAME=${TEST_NAME_BASE}-fallback-remote
run_ok "$TEST_NAME" cylc cat-log --debug -f e "${WORKFLOW_NAME}//1/a-task"
grep_ok "File not found locally, falling back to remote" "${TEST_NAME}.stderr"

#-------------------------------------------------------------------------------
purge
