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


# Test restarting a stalled workflow: stall timer should reset.

. "$(dirname "$0")/test_header"

grep_for_stall() {
  SUFFIX=$1
  grep_workflow_log_ok "grep-${SUFFIX}-1" 'Workflow stalled'
  grep_workflow_log_ok "grep-${SUFFIX}-2" 'PT2S stall timer starts NOW'
  grep_workflow_log_ok "grep-${SUFFIX}-3" 'stall timer timed out after PT2S'
  grep_workflow_log_ok "grep-${SUFFIX}-4" 'Workflow shutting down - "abort on stall timeout" is set'
}

set_test_number 12

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    [[events]]
        stall timeout = PT2S
        abort on stall timeout = True
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = false
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_fail "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --no-detach
grep_for_stall run

# Rinse and repeat
workflow_run_fail "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --no-detach
grep_workflow_log_ok grep-restart 'Run: \(re\)start number=2, log rollover=1' -E
grep_for_stall rstart

purge
