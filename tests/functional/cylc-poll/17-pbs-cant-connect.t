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
# Test poll PBS connection refused
BATCH_SYS_NAME="${TEST_NAME_BASE##??-}"
export REQUIRE_PLATFORM="batch:$BATCH_SYS_NAME"
. "$(dirname "$0")/test_header"

set_test_number 4

create_test_global_config "" "
[platforms]
  [[test-pbs-platform]]
    batch system = pbs
    hosts = ${CYLC_TEST_BATCH_TASK_HOST}
"


install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
if [[ "${CYLC_TEST_HOST}" != 'localhost' ]]; then
    # shellcheck disable=SC2029
    ssh -n "${CYLC_TEST_HOST}" "mkdir -p 'cylc-run/${SUITE_NAME}/'"
    rsync -a 'lib' "${CYLC_TEST_HOST}:cylc-run/${SUITE_NAME}/"
fi

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
# ssh security warnings may appear between outputs => check separately too.
sed -n 's/^.*\(\[jobs-poll err\]\) \(Connection refused\).*$/\1\n\2/p;
        s/^.*\(\[jobs-poll err\]\).*$/\1/p;
        s/^.*\(Connection refused\).*$/\1/p;
        s/^.*\(INFO - \[t1.1\] status=running: (polled)started\).*$/\1/p' \
    "${SUITE_RUN_DIR}/log/suite/log" >'sed-log.out'
contains_ok 'sed-log.out' <<'__LOG__'
[jobs-poll err]
Connection refused
__LOG__
contains_ok 'sed-log.out' <<'__LOG__'
INFO - [t1.1] status=running: (polled)started
__LOG__

purge
exit
