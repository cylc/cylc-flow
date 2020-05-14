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
# Test the run-functional-tests.sh --chunk option
. "$(dirname "$0")/test_header"
N_CHUNKS=2
set_test_number "$(( 2 + N_CHUNKS ))"
#-------------------------------------------------------------------------------
# list all tests
DRY_TEST_NAME="${TEST_NAME_BASE}-all"
CTB="${CYLC_REPO_DIR}/etc/bin/run-functional-tests"
run_ok "${DRY_TEST_NAME}" "${CTB}" --dry './tests'
# list tests for each chunk (from prove not run-functional-tests)
for i_chunk in $(seq "${N_CHUNKS}"); do
    TEST_NAME="${TEST_NAME_BASE}-chunk-${i_chunk}"
    run_ok "${TEST_NAME}" env CHUNK="${i_chunk}/${N_CHUNKS}" "${CTB}" --dry
    cat "${TEST_NAME}.stdout" >>'chunks.out'
done
# sort files ($CYLC_REPO_DIR/etc/bin/run-functional-tests.sh uses --shuffle)
sort -o "${DRY_TEST_NAME}.stdout" "${DRY_TEST_NAME}.stdout"
sort -o 'chunks.out' 'chunks.out'
# remove cd "$CYLC_HOME" lines
sed -i 's|^\./||' "${DRY_TEST_NAME}.stdout"
sed -i 's|^\./||' 'chunks.out'
# compare test plan for the full and chunked versions
cmp_ok "${DRY_TEST_NAME}.stdout" 'chunks.out'
exit
