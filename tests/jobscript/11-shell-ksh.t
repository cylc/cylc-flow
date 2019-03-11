#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Test job script OK with ksh. If ksh installed, assume ksh93.
. "$(dirname "${0}")/test_header"
if ! KSH="$(which ksh 2>/dev/null)"; then
    skip_all 'ksh not installed'
fi
set_test_number 5

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}" --set=KSH="${KSH}"
sed -in 's/WARNING - //p' "${TEST_NAME_BASE}-validate.stderr"
contains_ok "${TEST_NAME_BASE}-validate.stderr" <<__ERR__
deprecated: [runtime][foo][job]shell=${KSH}: use of ksh to run cylc task job file
__ERR__
run_ok "${TEST_NAME_BASE}-run" \
    cylc run "${SUITE_NAME}" --reference-test --debug --no-detach --set=KSH="${KSH}"
head -1 "${SUITE_RUN_DIR}/log/job/1/foo/NN/job" >'job-head.out'
cmp_ok 'job-head.out' <<<"#!${KSH} -l"
grep_ok 'Kornflakes' "${SUITE_RUN_DIR}/log/job/1/foo/NN/job.out"

purge_suite "${SUITE_NAME}"
exit
