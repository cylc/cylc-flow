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
# Test general task event handler + retry.
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
require_remote_platform
set_test_number 4

create_test_globalrc "" "
[platforms]
    [[${CYLC_REMOTE_PLATFORM}]]
        task event handler retry delays=3*PT1S
[task events]
    handlers=hello-event-handler '%(name)s' '%(event)s'
    handler events=succeeded, failed"

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate -s "PLATFORM=${CYLC_REMOTE_PLATFORM}" -s 'GLOBALCFG=True' "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach -s "PLATFORM=${CYLC_REMOTE_PLATFORM}" -s 'GLOBALCFG=True' \
    "${SUITE_NAME}"

LOG="${SUITE_RUN_DIR}/log/job/1/t1/NN/job-activity.log"
sed "/(('event-handler-00', 'succeeded'), 1)/!d; s/^.* \[/[/" "${LOG}" \
    >'edited-job-activity.log'
cmp_ok 'edited-job-activity.log' <<'__LOG__'
[(('event-handler-00', 'succeeded'), 1) cmd] hello-event-handler 't1' 'succeeded'
[(('event-handler-00', 'succeeded'), 1) ret_code] 1
[(('event-handler-00', 'succeeded'), 1) cmd] hello-event-handler 't1' 'succeeded'
[(('event-handler-00', 'succeeded'), 1) ret_code] 1
[(('event-handler-00', 'succeeded'), 1) cmd] hello-event-handler 't1' 'succeeded'
[(('event-handler-00', 'succeeded'), 1) ret_code] 0
[(('event-handler-00', 'succeeded'), 1) out] hello
__LOG__

grep 'event-handler-00.*will run after' "${SUITE_RUN_DIR}/log/suite/log" \
    | cut -d' ' -f 4-10 >'edited-log'
# Note: P0Y delays are not displayed
cmp_ok 'edited-log' <<'__LOG__'
1/t1/01 ('event-handler-00', 'succeeded') will run after PT1S
__LOG__

purge_suite_remote "${CYLC_REMOTE_PLATFORM}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
