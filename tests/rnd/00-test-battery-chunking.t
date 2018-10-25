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
#-------------------------------------------------------------------------------
# Test the cylc test-battery --chunk option
. $(dirname $0)/test_header
NO_CHUNKS=2
set_test_number $(( 2 + $NO_CHUNKS ))
#-------------------------------------------------------------------------------
# list all tests
DRY_TEST_NAME="$TEST_NAME_BASE-all"
run_ok "$DRY_TEST_NAME" cylc test-battery --dry
# list tests for each chunk (from prove not cylc test-battery)
temp_file=$(mktemp)
for chunk_no in $(seq $NO_CHUNKS); do
    TEST_NAME="$TEST_NAME_BASE-chunk-$chunk_no"
    run_ok "$TEST_NAME" cylc test-battery --chunk "$chunk_no/$NO_CHUNKS" --dry
    cat "$TEST_NAME.stdout" >> "$temp_file"
done
# sort files (cylc test-battery uses --shuffle)
sort -o "$DRY_TEST_NAME.stdout" "$DRY_TEST_NAME.stdout"
sort -o "$temp_file" "$temp_file"
# remove cd "$CYLC_HOME" lines
sed -i '/^cd "/d' "$DRY_TEST_NAME.stdout"
sed -i '/^cd "/d' "$temp_file"
# compare test plan for the full and chunked versions
cmp_ok "$DRY_TEST_NAME.stdout" "$temp_file"
