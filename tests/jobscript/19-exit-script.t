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

#------------------------------------------------------------------------------
# Test exit-script.

. "$(dirname "${0}")/test_header"
set_test_number 12

# 1) Should run on normal successful job exit.
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-success" \
  cylc run --debug --no-detach "${SUITE_NAME}"
grep_ok 'Cheesy peas!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.out"
grep_fail 'Oops!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.err"
purge_suite "${SUITE_NAME}"

# 2) Should not run on internal early EXIT.
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate --set=EXIT=true "${SUITE_NAME}"
run_fail "${TEST_NAME_BASE}-exit" \
  cylc run --debug --no-detach --set=EXIT=true "${SUITE_NAME}"
grep_fail 'Cheesy peas!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.out"
grep_ok 'EXIT Oops!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.err"
purge_suite "${SUITE_NAME}"

# 3) Should not run on external job TERM.
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate --set=NSLEEP=30 "${SUITE_NAME}"
cylc run --no-detach --set=NSLEEP=30 "${SUITE_NAME}" \
    <'/dev/null' 1>'/dev/null' 2>&1 &
SUITEPID=$!
STFILE="${SUITE_RUN_DIR}/log/job/1/foo/01/job.status"
for _ in {1..60}; do
    sleep 1
    if grep -q 'CYLC_JOB_INIT_TIME=' "${STFILE}" 2>'/dev/null'; then
        CYLC_JOB_PID="$(sed -n 's/^CYLC_JOB_PID=//p' "${STFILE}")"
        kill -s 'TERM' "${CYLC_JOB_PID}"
        break
    fi
done
if wait "${SUITEPID}"; then
    fail "${TEST_NAME_BASE}-term"  # Fail if suite returns zero
else
    ok "${TEST_NAME_BASE}-term"    # OK if suite returns non-zero
fi
grep_fail 'Cheesy peas!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.out"
grep_ok 'TERM Oops!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.err"
purge_suite "${SUITE_NAME}"

exit
