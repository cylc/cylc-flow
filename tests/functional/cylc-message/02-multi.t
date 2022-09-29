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

#------------------------------------------------------------------------------
# Test "cylc message" with multiple messages.

export REQUIRE_PLATFORM='loc:* comms:?(tcp|ssh)'
. "$(dirname "$0")/test_header"

set_test_number 3
init_workflow "${TEST_NAME_BASE}" <<__FLOW__
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        platform = $CYLC_TEST_PLATFORM
        script = """
            cylc__job__wait_cylc_message_started
            cylc message -p WARNING "\${CYLC_WORKFLOW_ID}" "\${CYLC_TASK_JOB}" \
                "Warn this" "INFO: Greeting" - <<'__MESSAGES__'
            Warn that

            DEBUG: Remove stuffs such as
            badness
            slowness
            and other incorrectness.

            CUSTOM: whatever
            __MESSAGES__
        """
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --debug --no-detach "${WORKFLOW_NAME}"

LOG="${WORKFLOW_RUN_DIR}/log/scheduler/log"
sed -r -n -e 's/^.* ([A-Z]+ .* \(received\).*$)/\1/p' \
       -e '/badness|slowness|and other incorrectness/p' \
    "${LOG}" >'sed.out'
sed -i 's/\(^.*\) at .*$/\1/;' 'sed.out'

# Note: the continuation bit gets printed twice, because the message gets a
# warning as being unhandled.
cmp_ok 'sed.out' <<__LOG__
DEBUG - [1/foo submitted job:01 flows:1] (received)started
WARNING - [1/foo running job:01 flows:1] (received)Warn this
INFO - [1/foo running job:01 flows:1] (received)Greeting
WARNING - [1/foo running job:01 flows:1] (received)Warn that
DEBUG - [1/foo running job:01 flows:1] (received)Remove stuffs such as
${LOG_INDENT}badness
${LOG_INDENT}slowness
${LOG_INDENT}and other incorrectness.
${LOG_INDENT}badness
${LOG_INDENT}slowness
${LOG_INDENT}and other incorrectness.
INFO - [1/foo running job:01 flows:1] (received)whatever
DEBUG - [1/foo running job:01 flows:1] (received)succeeded
__LOG__

purge
exit
