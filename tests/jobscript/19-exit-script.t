#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
set_test_number 9

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

# 1) Should run on normal successful job exit.
run_ok "${TEST_NAME_BASE}-run" \
  cylc run --debug --no-detach "${SUITE_NAME}" 
grep_ok 'Cheesy peas!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.out"
grep_fail 'Oops!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.err"

# 2) Should not run on internal early EXIT.
run_fail "${TEST_NAME_BASE}-run" \
  cylc run --debug --no-detach --set=EXIT=true "${SUITE_NAME}" 
grep_fail 'Cheesy peas!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.out"
grep_ok 'EXIT Oops!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.err"

# 3) Should not run on external job TERM.
cylc run --set=NSLEEP=30 "${SUITE_NAME}"
sleep 3
CYLC_JOB_PID=$(sed -n 's/^CYLC_JOB_PID=//p' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.status")
kill -s TERM $CYLC_JOB_PID
sleep 5
grep_fail 'Cheesy peas!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.out"
grep_ok 'TERM Oops!' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.err"

purge_suite "${SUITE_NAME}"
