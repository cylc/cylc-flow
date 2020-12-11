#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

# Test deprecated batch_sys_job_id & batch_sys_name event handler template vars
# - they should still work but give a validation warning

. "$(dirname "$0")/test_header"
set_test_number 5

init_suite "${TEST_NAME_BASE}" << __FLOW__
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        [[[events]]]
            started handler = echo "job_id = %(batch_sys_job_id)s ; job_runner_name = %(batch_sys_name)s"
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

grep_ok 'WARNING - The event handler template variable "%(batch_sys_job_id)s" is deprecated - use "%(job_id)s" instead' \
    "${TEST_NAME_BASE}-validate.stderr" -F
grep_ok 'WARNING - The event handler template variable "%(batch_sys_name)s" is deprecated - use "%(job_runner_name)s" instead' \
    "${TEST_NAME_BASE}-validate.stderr" -F

suite_run_ok "${TEST_NAME_BASE}-run" cylc run --no-detach "${SUITE_NAME}"
poll_suite_stopped

FOO_ACTIVITY_LOG="${SUITE_RUN_DIR}/log/job/1/foo/NN/job-activity.log"
grep_ok "\[(('event-handler-00', 'started'), 1) out\] job_id = [0-9]\+ ; job_runner_name = background" "$FOO_ACTIVITY_LOG"

purge
exit
