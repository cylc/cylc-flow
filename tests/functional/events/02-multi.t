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
#-------------------------------------------------------------------------------
# Test list of multiple event handlers.

. "$(dirname "$0")/test_header"

set_test_number 3

init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[scheduling]
   [[graph]]
      R1 = t1
[runtime]
    [[t1]]
        script=true
        [[[events]]]
            started handler = echo %(suite)s, echo %(name)s, echo %(start_time)s
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"
JOB_STFILE="${SUITE_RUN_DIR}/log/job/1/t1/01/job.status"
JOB_START_TIME="$(sed -n 's/^CYLC_JOB_INIT_TIME=//p' "${JOB_STFILE}")"
cylc cat-log "${SUITE_NAME}" \
    | sed -n -e 's/^.*\(\[(('"'"'event-handler-0.'"'"'.*$\)/\1/p' | sort >'log'

cmp_ok log <<__END__
[(('event-handler-00', 'started'), 1) cmd] echo ${SUITE_NAME}
[(('event-handler-00', 'started'), 1) out] ${SUITE_NAME}
[(('event-handler-00', 'started'), 1) ret_code] 0
[(('event-handler-01', 'started'), 1) cmd] echo t1
[(('event-handler-01', 'started'), 1) out] t1
[(('event-handler-01', 'started'), 1) ret_code] 0
[(('event-handler-02', 'started'), 1) cmd] echo ${JOB_START_TIME}
[(('event-handler-02', 'started'), 1) out] ${JOB_START_TIME}
[(('event-handler-02', 'started'), 1) ret_code] 0
__END__

purge_suite "${SUITE_NAME}"
exit
