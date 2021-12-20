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
# Test "cylc cat-log" for remote tasks with auto-retrieval.
export REQUIRE_PLATFORM='loc:remote fs:indep'
. "$(dirname "$0")/test_header"
set_test_number 7

create_test_global_config "" "
[platforms]
   [[${CYLC_TEST_PLATFORM}]]
       retrieve job logs = True"
install_workflow "${TEST_NAME_BASE}" remote-simple

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play --debug --no-detach "${WORKFLOW_NAME}"

# Local job.out should exist (retrieved).
LOCAL_JOB_OUT=$(cylc cat-log -f a -m d "${WORKFLOW_NAME}//1/a-task")/job.out
exists_ok "${LOCAL_JOB_OUT}"

# Distinguish local from remote job.out
perl -pi -e 's/fox/FOX/' "${LOCAL_JOB_OUT}"

# Cat the remote one.
TEST_NAME=${TEST_NAME_BASE}-out-rem
run_ok "${TEST_NAME}" cylc cat-log --force-remote -f o \
    "${WORKFLOW_NAME}//1/a-task"
grep_ok '^the quick brown fox$' "${TEST_NAME}.stdout"

# Cat the local one.
TEST_NAME=${TEST_NAME_BASE}-out-loc
run_ok "${TEST_NAME}" cylc cat-log -f o "${WORKFLOW_NAME}//1/a-task"
grep_ok '^the quick brown FOX$' "${TEST_NAME}.stdout"

purge
exit
