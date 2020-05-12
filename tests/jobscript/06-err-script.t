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
# Test err-script.
. "$(dirname "${0}")/test_header"
set_test_number 4

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}" --reference-test --debug --no-detach
grep_ok 'EXIT foo bar baz qux' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.err"
run_fail "${TEST_NAME_BASE}-grep-02" \
    grep -q -F 'ERR foo bar baz qux' "${SUITE_RUN_DIR}/log/job/1/foo/02/job.err"

for I in 13 37 61; do
    create_test_globalrc '' "
[job platforms]
    [[pbshost]]
        remote hosts = localhost
        batch system = pbs
        job name length maximum = ${I}"
    run_ok "${TEST_NAME_BASE}-${I}" cylc jobscript "${SUITE_NAME}" \
        "abcdefghijklmnopqrstuvwxyz_0123456789.1"
    contains_ok "${TEST_NAME_BASE}-${I}.stdout" <<__OUT__
#PBS -N $(cut -c1-${I} <<<"abcdefghijklmnopqrstuvwxyz_0123456789.1.${SUITE_NAME}")
__OUT__
done
purge_suite "${SUITE_NAME}"
exit
