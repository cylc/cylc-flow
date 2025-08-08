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

# Test the --format option.

. "$(dirname "$0")/test_header"
set_test_number 6

init_workflow "${TEST_NAME_BASE}" << '__EOF__'
[scheduler]
  [[events]]
    stall timeout = PT0S
    abort on stall timeout = True
[scheduling]
  [[graph]]
    R1 = foo
[runtime]
  [[foo]]
    pre-script = """
      cylc broadcast "$CYLC_WORKFLOW_ID" \
        -p "$CYLC_TASK_CYCLE_POINT" -n "$CYLC_TASK_NAME" \
        --set '[environment]horse=dorothy' \
        --set 'post-script=echo "$horse"'
    """
    script = """
      cylc broadcast "$CYLC_WORKFLOW_ID" --display --format json > out.json
      cylc broadcast "$CYLC_WORKFLOW_ID" --display --format raw > raw1.stdout
      # Test deprecated option:
      cylc broadcast "$CYLC_WORKFLOW_ID" --display --raw 1> raw2.stdout 2> raw2.stderr
    """
__EOF__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --no-detach

FOO_WORK_DIR="${WORKFLOW_RUN_DIR}/work/1/foo"

TEST_NAME="${TEST_NAME_BASE}-cmp-json"
cmp_json "$TEST_NAME" "${FOO_WORK_DIR}/out.json" << '__EOF__'
{
  "1": {
    "foo": {
      "environment": {
        "horse": "dorothy"
      },
      "post-script": "echo \"$horse\""
    }
  }
}
__EOF__

cmp_ok "${FOO_WORK_DIR}/raw1.stdout" << '__EOF__'
{'1': {'foo': {'environment': {'horse': 'dorothy'}, 'post-script': 'echo "$horse"'}}}
__EOF__

cmp_ok "${FOO_WORK_DIR}/raw2.stdout" "${FOO_WORK_DIR}/raw1.stdout"

cmp_ok "${FOO_WORK_DIR}/raw2.stderr" << __EOF__
DEPRECATED: the --raw option will be removed at Cylc 8.7; use --format=raw instead.
__EOF__

purge
