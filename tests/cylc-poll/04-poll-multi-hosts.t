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
# Test poll multiple jobs on localhost and a remote host
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
require_remote_platform
set_test_number 3

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"

RUN_DIR="$RUN_DIR/${SUITE_NAME}"
LOG="${RUN_DIR}/log/suite/log"
sed -n 's/^.*\(cylc jobs-poll\)/\1/p' "${LOG}" | sort -u >'edited-suite-log'

sort >'edited-suite-log-ref' <<__LOG__
cylc jobs-poll --debug -- '\$HOME/cylc-run/${SUITE_NAME}/log/job' 1/remote-fail-1/01 1/remote-success-1/01 1/remote-success-2/01
cylc jobs-poll --debug -- '\$HOME/cylc-run/${SUITE_NAME}/log/job' 1/local-fail-1/01 1/local-fail-2/01 1/local-success-1/01
__LOG__
cmp_ok 'edited-suite-log' 'edited-suite-log-ref'

purge_suite_remote "${CYLC_TEST_HOST}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
