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
# Test that known task outputs can be used as events.

. "$(dirname "$0")/test_header"

set_test_number 4

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduling]
   [[graph]]
      R1 = t1
[runtime]
    [[t1]]
        script="""
cylc message -- ${CYLC_WORKFLOW_ID} ${CYLC_TASK_JOB} \
    'rose' 'lily' 'iris' 'WARNING:poison ivy'
"""
        [[[outputs]]]
            rose = rose
            lily = lily
            iris = iris
        [[[events]]]
            handler events = rose, lily, iris, warning, arsenic
            # (arsenic is an invalid event)
            handlers = echo %(message)s
__FLOW_CONFIG__

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "$TEST_NAME" cylc validate "${WORKFLOW_NAME}"

dump_std "${TEST_NAME}"
grep_ok 'WARNING - Invalid event name.*arsenic' "${TEST_NAME}.stderr"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"
cylc cat-log "${WORKFLOW_NAME}" \
    | sed -n -e 's/^.*\(\[(('"'"'event-handler-00'"'"'.*$\)/\1/p' | sort >'log'

cmp_ok log <<__END__
[(('event-handler-00', 'iris'), 1) cmd] echo iris
[(('event-handler-00', 'iris'), 1) out] iris
[(('event-handler-00', 'iris'), 1) ret_code] 0
[(('event-handler-00', 'lily'), 1) cmd] echo lily
[(('event-handler-00', 'lily'), 1) out] lily
[(('event-handler-00', 'lily'), 1) ret_code] 0
[(('event-handler-00', 'rose'), 1) cmd] echo rose
[(('event-handler-00', 'rose'), 1) out] rose
[(('event-handler-00', 'rose'), 1) ret_code] 0
[(('event-handler-00', 'warning-1'), 1) cmd] echo 'poison ivy'
[(('event-handler-00', 'warning-1'), 1) out] poison ivy
[(('event-handler-00', 'warning-1'), 1) ret_code] 0
__END__

purge
exit
