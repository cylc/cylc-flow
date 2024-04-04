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
# Test list of multiple event handlers.

. "$(dirname "$0")/test_header"

set_test_number 3

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    [[events]]
        inactivity timeout = PT30S
[scheduling]
    [[graph]]
        R1 = t1
[runtime]
    [[t1]]
        script = true
        [[[events]]]
            started handlers = echo %(workflow)s, echo %(name)s, echo %(start_time)s
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"
JOB_STFILE="${WORKFLOW_RUN_DIR}/log/job/1/t1/01/job.status"
JOB_START_TIME="$(sed -n 's/^CYLC_JOB_INIT_TIME=//p' "${JOB_STFILE}")"
cylc cat-log "${WORKFLOW_NAME}" \
    | sed -n -e 's/^.*\(\[(('"'"'event-handler-0.'"'"'.*$\)/\1/p' | sort >'log'

cmp_ok log <<__END__
[(('event-handler-00', 'started'), 1) cmd] echo ${WORKFLOW_NAME}
[(('event-handler-00', 'started'), 1) out] ${WORKFLOW_NAME}
[(('event-handler-00', 'started'), 1) ret_code] 0
[(('event-handler-01', 'started'), 1) cmd] echo t1
[(('event-handler-01', 'started'), 1) out] t1
[(('event-handler-01', 'started'), 1) ret_code] 0
[(('event-handler-02', 'started'), 1) cmd] echo ${JOB_START_TIME}
[(('event-handler-02', 'started'), 1) out] ${JOB_START_TIME}
[(('event-handler-02', 'started'), 1) ret_code] 0
__END__

purge
exit
