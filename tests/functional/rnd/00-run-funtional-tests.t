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
# Test the run-functional-tests --chunk option
. "$(dirname "$0")/test_header"
set_test_number 16
#-------------------------------------------------------------------------------

CTB="${CYLC_REPO_DIR}/etc/bin/run-functional-tests"
unset CHUNK

# ensure that 'tests/f' is used as the default test base
TEST_NAME="${TEST_NAME_BASE}-base"
run_ok "${TEST_NAME}-1" "$CTB" --dry
run_ok "${TEST_NAME}-2" "$CTB" --dry tests/functional
sort -o "${TEST_NAME}-1.stdout" "${TEST_NAME}-1.stdout"
sort -o "${TEST_NAME}-2.stdout" "${TEST_NAME}-2.stdout"
cmp_ok "${TEST_NAME}-1.stdout" "${TEST_NAME}-2.stdout"

TEST_NAME="${TEST_NAME_BASE}-chunk-base"
run_ok "${TEST_NAME}-1" env CHUNK="1/4" "$CTB" --dry
run_ok "${TEST_NAME}-2" env CHUNK="1/4" "$CTB" --dry tests/functional
sort -o "${TEST_NAME}-1.stdout" "${TEST_NAME}-1.stdout"
sort -o "${TEST_NAME}-2.stdout" "${TEST_NAME}-2.stdout"
cmp_ok "${TEST_NAME}-1.stdout" "${TEST_NAME}-2.stdout"

# ensure that mixing test bases works correctly
TEST_NAME="${TEST_NAME_BASE}-testbase"
run_ok "${TEST_NAME}-1" "$CTB" --dry tests/f
run_ok "${TEST_NAME}-2" "$CTB" --dry tests/k
run_ok "${TEST_NAME}-3" "$CTB" --dry tests/f tests/k
cat "${TEST_NAME}-2.stdout" >> "${TEST_NAME}-1.stdout"
sort -o "${TEST_NAME}-1.stdout" "${TEST_NAME}-1.stdout"
sort -o "${TEST_NAME}-3.stdout" "${TEST_NAME}-3.stdout"
cmp_ok "${TEST_NAME}-1.stdout" "${TEST_NAME}-3.stdout"

# ensure that the whole is equal to the sum of its parts
N_CHUNKS=4
DRY_TEST_NAME="${TEST_NAME_BASE}-all"
run_ok "${DRY_TEST_NAME}" "${CTB}" --dry 'tests/f' 'tests/k'
# list tests for each chunk (from prove not run-functional-tests)
for i_chunk in $(seq "${N_CHUNKS}"); do
    TEST_NAME="${TEST_NAME_BASE}-chunk_n-${i_chunk}"
    run_ok "${TEST_NAME}" env CHUNK="${i_chunk}/${N_CHUNKS}" "${CTB}" --dry 'tests/f' 'tests/k'
    cat "${TEST_NAME}.stdout" >>'chunks.out'
done
# sort files ($CYLC_REPO_DIR/etc/bin/run-functional-tests uses --shuffle)
sort -o "${DRY_TEST_NAME}.stdout" "${DRY_TEST_NAME}.stdout"
sort -o 'chunks.out' 'chunks.out'
# compare test plan for the full and chunked versions
cmp_ok "${DRY_TEST_NAME}.stdout" 'chunks.out'

exit
