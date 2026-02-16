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
#------------------------------------------------------------------------

. "$(dirname "$0")/test_header"

set_test_number 16

for change_type in reload restart; do
  init_workflow "${TEST_NAME_BASE}-${change_type}" <<__FLOW_CONFIG__
[scheduler]
  allow implicit tasks = True
  [[events]]
    stall timeout = PT0S
    abort on stall timeout = True
    inactivity timeout = PT60S
    abort on inactivity timeout = True

[scheduling]
  cycling mode = integer
  initial cycle point = 1
  stop after cycle point = 3
  runahead limit = P1
  [[xtriggers]]
    xtrig = xrandom(100, sequential=True)
  [[graph]]
    P1 = """
      @xtrig => a1  # MARKER
      a1 & a2 => b & z:started => c  # MARKER
      b[-P1] => b
    """
    R1/2 = b => stop

[runtime]
  [[z]]
    script = sleep 60
  [[b]]
    script = """
      if [[ \$CYLC_TASK_CYCLE_POINT == 2 ]]; then
        cylc__job__poll_grep_workflow_log -E '1/c.*succeeded'
        cylc__job__poll_grep_workflow_log -E '1/z.*running'
        cylc__job__poll_grep_workflow_log -E '2/z.*running'

        sed -i 's/.*MARKER/      d => b => e /' "\$CYLC_WORKFLOW_RUN_DIR/flow.cylc"
        if [[ $change_type == reload ]]; then
          cylc reload "\$CYLC_WORKFLOW_ID"
        else
          cylc stop --now --now "\$CYLC_WORKFLOW_ID"
          sleep 1
          cylc play "\$CYLC_WORKFLOW_ID"
        fi
      fi
    """
  [[stop]]
    script = """
        cylc__job__poll_grep_workflow_log -E '2/e.*running'
        cylc stop "\${CYLC_WORKFLOW_ID}"
    """
__FLOW_CONFIG__


  workflow_run_ok "${TEST_NAME_BASE}-${change_type}-run" cylc play -N "${WORKFLOW_NAME}"
  if [[ $change_type == restart ]]; then
    sleep 5
    poll_workflow_stopped
  fi

  TEST_NAME="${TEST_NAME_BASE}-${change_type}-tree"
  LOG_DIR="${HOME}/cylc-run/${WORKFLOW_NAME}/log"
  run_ok "$TEST_NAME" tree -L 2 --noreport --charset=ascii "${LOG_DIR}/job"
  sed -i '1d' "${TEST_NAME}.stdout"
  cmp_ok "${TEST_NAME}.stdout" << '__OUT__'
|-- 1
|   |-- a1
|   |-- a2
|   |-- b
|   |-- c
|   `-- z
`-- 2
    |-- a1
    |-- a2
    |-- b
    |-- e
    |-- stop
    `-- z
__OUT__

  grep_ok 'jobs-kill' "${LOG_DIR}/job/1/z/01/job-activity.log"
  grep_ok 'jobs-kill' "${LOG_DIR}/job/2/z/01/job-activity.log"
  grep_ok 'succeeded' "${LOG_DIR}/job/2/e/01/job.out"

  TEST_NAME="${TEST_NAME_BASE}-${change_type}-db"
  run_ok "$TEST_NAME" sqlite3 "${LOG_DIR}/db" "SELECT name, cycle, status FROM task_pool;"
  cmp_ok "${TEST_NAME}.stdout" << __HERE__
b|3|waiting
__HERE__

  purge
done

exit
