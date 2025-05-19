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
# Cylc profile test
# NOTE: This test will run the Cylc profiler on the given test platform.
# The test platform may need to be configured for this to work (e.g.
# "cgroups path" may need to be set).
export REQUIRE_PLATFORM='runner:?(pbs|slurm) comms:tcp'
. "$(dirname "$0")/test_header"
set_test_number 8

create_test_global_config "
[platforms]
  [[${CYLC_TEST_PLATFORM}]]
    [[[profile]]]
      activate = True
      polling interval = 1
  [[localhost]]
    [[[profile]]]
      activate = True
      cgroups path = /no/such/path
"

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
#!Jinja2

[scheduling]
    [[graph]]
        R1 = the_good & the_bad? & the_ugly

[runtime]
    [[the_good]]
        # this task should succeeded normally
        platform = {{ environ['CYLC_TEST_PLATFORM'] }}
        script = sleep 1
    [[the_bad]]
        # this task should fail (it should still send profiling info)
        platform = {{ environ['CYLC_TEST_PLATFORM'] }}
        script = sleep 5; false
    [[the_ugly]]
        # this task should succeed despite the broken profiler configuration
        platform = localhost
        script = sleep 1
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --debug --no-detach "${WORKFLOW_NAME}"

# ensure the cpu and memory messages were received and that these messages
# were received before the succeeded message
log_scan "${TEST_NAME_BASE}-task-succeeded" \
    "${WORKFLOW_RUN_DIR}/log/scheduler/log" 1 0 \
    '1/the_good.*(received)cpu_time.*max_rss*' \
    '1/the_good.*(received)succeeded'

# ensure the cpu and memory messages were received and that these messages
# were received before the failed message
log_scan "${TEST_NAME_BASE}-task-succeeded" \
    "${WORKFLOW_RUN_DIR}/log/scheduler/log" 1 0 \
    '1/the_bad.*(received)cpu_time.*max_rss*' \
    '1/the_bad.*(received)failed'

# ensure this task succeeded despite the broken profiler configuration
grep_workflow_log_ok "${TEST_NAME_BASE}-broken" '1/the_ugly.*(received)succeeded'
grep_ok 'FileNotFoundError: Cgroup not found' "$(cylc cat-log "${WORKFLOW_NAME}//1/the_ugly" -f e -m p)"

purge
