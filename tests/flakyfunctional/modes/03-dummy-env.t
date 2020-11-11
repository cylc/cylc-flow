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
# Test that user environment is disabled along with env-script in dummy mode.
# And that remote host is disabled in dummy local mode.
. "$(dirname "$0")/test_header"
set_test_number 5

install_suite "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"\
        --mode=dummy-local

# Check that each of pre, main and post script do not leave a trace in the
# job out when --mode=dummy-local.
declare -a GREPFOR=('MY-PRE-SCRIPT' 'MY-SCRIPT' 'MY-POST-SCRIPT')
for BAD_PHRASE in "${GREPFOR[@]}"; do
    cp "${SUITE_RUN_DIR}/log/job/1/oxygas/NN/job.out" "${BAD_PHRASE}"
    grep_fail "${BAD_PHRASE}" "${BAD_PHRASE}"
done

purge
exit
