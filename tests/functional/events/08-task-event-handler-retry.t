#!/bin/bash
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
. "$(dirname "$0")/test_header"
set_test_number 3

OPT_SET=
if [[ "${TEST_NAME_BASE}" == *-globalcfg ]]; then
    create_test_globalrc "" "
[task events]
    handlers = hello-event-handler %(name)s %(event)s %(suite_url)s %(suite_uuid)s %(task_url)s %(message)s %(point)s %(submit_num)s %(id)s
    handler events=succeeded, failed
    handler retry delays=PT0S, 2*PT1S"
    OPT_SET='-s GLOBALCFG=True'
fi
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-validate" cylc validate ${OPT_SET} "${SUITE_NAME}"
# shellcheck disable=SC2086
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach ${OPT_SET} "${SUITE_NAME}"

SUITE_URL=http://my-suites.com/${SUITE_NAME}.html
TASK_URL=http://my-suites.com/${SUITE_NAME}/t1.html
LOGD="${SUITE_RUN_DIR}/log"
SUITE_UUID="$(sqlite3 "${LOGD}/db" 'SELECT value FROM suite_params WHERE key=="uuid_str"')"
LOG="${LOGD}/job/1/t1/NN/job-activity.log"
sed "/(('event-handler-00', 'succeeded'), 1)/!d; s/^.* \[/[/" "${LOG}" \
    >'edited-job-activity.log'
cmp_ok 'edited-job-activity.log' <<__LOG__
[(('event-handler-00', 'succeeded'), 1) cmd] hello-event-handler t1 succeeded ${SUITE_URL} ${SUITE_UUID} ${TASK_URL} 'job succeeded' 1 1 t1.1
[(('event-handler-00', 'succeeded'), 1) ret_code] 1
[(('event-handler-00', 'succeeded'), 1) cmd] hello-event-handler t1 succeeded ${SUITE_URL} ${SUITE_UUID} ${TASK_URL} 'job succeeded' 1 1 t1.1
[(('event-handler-00', 'succeeded'), 1) ret_code] 1
[(('event-handler-00', 'succeeded'), 1) cmd] hello-event-handler t1 succeeded ${SUITE_URL} ${SUITE_UUID} ${TASK_URL} 'job succeeded' 1 1 t1.1
[(('event-handler-00', 'succeeded'), 1) ret_code] 0
[(('event-handler-00', 'succeeded'), 1) out] hello
__LOG__

purge_suite "${SUITE_NAME}"
exit
