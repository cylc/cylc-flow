#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
# Test that grep_fail fails if test is not there:
. "$(dirname "$0")/test_header"

set_test_number 3

echo "The finger writes, and having writ moves on." > test_file.txt

# It passes if file exists and search term not there:
grep_fail 'foo' 'test_file.txt'

# It fails if the file exists and the search term is there:
grep_fail 'writ' 'test_file.txt' | tee "out1" > /dev/null
grep_ok 'not ok 2 - test_file.txt-grep-fail' 'out1'

# It fails if the file does not exist:
grep_fail "writ" "test_file2.txt" | tee "out2" > /dev/null
grep_ok 'not ok 3 - test_file2.txt-grep-fail-file to be grepped does not exist.' 'out2'
