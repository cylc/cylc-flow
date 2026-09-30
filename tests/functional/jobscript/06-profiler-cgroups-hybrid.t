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
# Cylc profiler test for a node running cgroups in systemd "hybrid" mode: a
# cgroup2 hierarchy is mounted for process tracking only (cgroup.controllers
# is empty) so the profiler must ignore its readable-but-wrong cpu.stat and
# use the v1 data for both controllers.

. "$(dirname "$0")/test_header"

if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    skip_all "Tests not compatible with $OSTYPE"
fi

set_test_number 8

CGROUP_NAME='pbspro.service/jobid/2397344.ehz100'
SERVICE_CGROUP='system.slice/pbs.service'
ROOT="${PWD}/cgroups_test_data"

# v2 (unified) hierarchy: process tracking only. cgroup.controllers is
# empty (no resource controllers), but the kernel still exposes cpu.stat -
# for the batch system's service cgroup, shared by every job on the node.
mkdir -p "${ROOT}/${SERVICE_CGROUP}"
printf "" > "${ROOT}/${SERVICE_CGROUP}/cgroup.controllers"
printf "usage_usec 81514978331" > "${ROOT}/${SERVICE_CGROUP}/cpu.stat"

# v1 hierarchies: the real per-job data. The cpu and cpuacct controllers
# are co-mounted as "cpu,cpuacct".
mkdir -p "${ROOT}/memory/${CGROUP_NAME}" "${ROOT}/cpu,cpuacct/${CGROUP_NAME}"
echo 'total_rss 12345678' > "${ROOT}/memory/${CGROUP_NAME}/memory.stat"
echo '123456789' > "${ROOT}/memory/${CGROUP_NAME}/memory.limit_in_bytes"
# cgroups v1 reports CPU usage in nanoseconds
echo '56781234000' > "${ROOT}/cpu,cpuacct/${CGROUP_NAME}/cpuacct.usage"

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

# All three values must come from the v1 files. In particular cpu_time must
# be 56781 (the job's cpuacct.usage) and NOT 81514978 (the whole PBS
# service, from the v2 cpu.stat).
grep_workflow_log_ok "${TEST_NAME_BASE}-the_good-data" \
    '1/the_good.*(received)_cylc_profiler.*"max_rss": 12345678.*"cpu_time": 56781.*"memory_allocated": 123456789'
grep_workflow_log_ok "${TEST_NAME_BASE}-the_bad-data" \
    '1/the_bad.*(received)_cylc_profiler.*"max_rss": 12345678.*"cpu_time": 56781.*"memory_allocated": 123456789'

purge

