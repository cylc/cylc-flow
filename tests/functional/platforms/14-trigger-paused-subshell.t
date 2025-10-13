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

# Triggering a task with a subshell platform setting while the workflow is
# paused should only evaluate the subshell once.
# Here we have a subshell command that alternates between two platforms on each
# call, to check the platform does not change during a manual trigger.
# https://github.com/cylc/cylc-flow/issues/6994

export REQUIRE_PLATFORM='loc:remote'

. "$(dirname "$0")/test_header"
set_test_number 11

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

local_host_name=$(hostname)
remote_host_name=$(cylc config -i "[platforms][${CYLC_TEST_PLATFORM}]hosts")
workflow_log="${WORKFLOW_RUN_DIR}/log/scheduler/log"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
cylc play "${WORKFLOW_NAME}" --pause
poll_grep_workflow_log "1/foo:waiting"

cylc trigger "${WORKFLOW_NAME}//1/foo"

log_scan "log-grep-01" "$workflow_log" 10 2 \
    "\[1/foo/01:preparing\] submitted to localhost" \
    "\[1/foo/01:.*\] (received)${local_host_name}" \
    "\[1/foo/01:.*\] => succeeded"

cylc trigger "${WORKFLOW_NAME}//1/foo"

log_scan "log-grep-02" "$workflow_log" 10 2 \
    "\[1/foo/02:preparing\] submitted to ${CYLC_TEST_PLATFORM}" \
    "\[1/foo/02:.*\] (received)${remote_host_name}" \
    "\[1/foo/02:.*\] => succeeded"

cylc trigger "${WORKFLOW_NAME}//1/foo"

log_scan "log-grep-03" "$workflow_log" 10 2 \
    "\[1/foo/03:preparing\] submitted to localhost" \
    "\[1/foo/03:.*\] (received)${local_host_name}" \
    "\[1/foo/03:.*\] => succeeded"

cylc stop "${WORKFLOW_NAME}" --now --now

# Check DB as well:
sqlite3 "${WORKFLOW_RUN_DIR}/.service/db" \
    "SELECT submit_num, platform_name FROM task_jobs" > task_jobs.out
cmp_ok task_jobs.out <<__EOF__
1|localhost
2|${CYLC_TEST_PLATFORM}
3|localhost
__EOF__

poll_workflow_stopped
purge
