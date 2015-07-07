#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug "${SUITE_NAME}"

SUITE_RUN_DIR="$(cylc get-global-config '--print-run-dir')"
LOG="${SUITE_RUN_DIR}/${SUITE_NAME}/log/job/1/t1/NN/job-activity.log"
sed "/('event-handler-00', 'succeeded', '01')/!d; s/^.* \[/[/" "${LOG}" \
    >'edited-job-activity.log'
cmp_ok 'edited-job-activity.log' <<'__LOG__'
[('event-handler-00', 'succeeded', '01') cmd] hello-event-handler 't1' 'succeeded'
[('event-handler-00', 'succeeded', '01') ret_code] 1
[('event-handler-00', 'succeeded', '01') cmd] hello-event-handler 't1' 'succeeded'
[('event-handler-00', 'succeeded', '01') ret_code] 1
[('event-handler-00', 'succeeded', '01') cmd] hello-event-handler 't1' 'succeeded'
[('event-handler-00', 'succeeded', '01') ret_code] 0
[('event-handler-00', 'succeeded', '01') out] hello
__LOG__

purge_suite "${SUITE_NAME}"
exit
