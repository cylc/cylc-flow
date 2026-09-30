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
# Cylc profile test for a node running cgroups in "hybrid" mode, where the
# cpu controller is served by the unified (v2) hierarchy but the memory
# controller is only available from the v1 hierarchy. The profiler must pick
# the version for each controller independently.

. "$(dirname "$0")/test_header"

if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    skip_all "Tests not compatible with $OSTYPE"
fi

set_test_number 8

CGROUP_NAME='pbspro.service/jobid/2397344.ehz100'
ROOT="${PWD}/cgroups_test_data"

# v2 (unified) hierarchy: provides cpu.stat but NO memory files
mkdir -p "${ROOT}/${CGROUP_NAME}"
printf "blah blah 123456\nusage_usec 56781234" > "${ROOT}/${CGROUP_NAME}/cpu.stat"

# v1 hierarchy: provides the memory controller only
mkdir -p "${ROOT}/memory/${CGROUP_NAME}"
echo 'total_rss 12345678' > "${ROOT}/memory/${CGROUP_NAME}/memory.stat"
echo '123456789' > "${ROOT}/memory/${CGROUP_NAME}/memory.limit_in_bytes"

export profiler_test_env_var="/${CGROUP_NAME}"
create_test_global_config "
[platforms]
  [[localhost]]
    [[[profiler]]]
      activate = True
      cgroups path = ${ROOT}
"

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
#!Jinja2

[scheduling]
    [[graph]]
        R1 = the_good & the_bad?

[runtime]
    [[the_good]]
        # this task should succeeded normally
        platform = localhost
        script = sleep 5
    [[the_bad]]
        # this task should fail (it should still send profiling info)
        platform = localhost
        script = sleep 5; false
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --debug --no-detach "${WORKFLOW_NAME}"

# ensure the cpu and memory messages were received and that these messages
# were received before the succeeded message
log_scan "${TEST_NAME_BASE}-task-succeeded" \
    "${WORKFLOW_RUN_DIR}/log/scheduler/log" 1 0 \
    '1/the_good.*(received)_cylc_profiler.*cpu_time' \
    '1/the_good.*(received)succeeded'

# ensure the cpu and memory messages were received and that these messages
# were received before the failed message
log_scan "${TEST_NAME_BASE}-task-failed" \
    "${WORKFLOW_RUN_DIR}/log/scheduler/log" 1 0 \
    '1/the_bad.*(received)_cylc_profiler.*cpu_time' \
    '1/the_bad.*failed'

# cpu_time must come from the v2 cpu.stat (usage_usec, microseconds) and
# max_rss / memory_allocated from the v1 memory files
grep_workflow_log_ok "${TEST_NAME_BASE}-the_good-data" \
    '1/the_good.*(received)_cylc_profiler.*"max_rss": 12345678.*"cpu_time": 56781.*"memory_allocated": 123456789'
grep_workflow_log_ok "${TEST_NAME_BASE}-the_bad-data" \
    '1/the_bad.*(received)_cylc_profiler.*"max_rss": 12345678.*"cpu_time": 56781.*"memory_allocated": 123456789'

purge

