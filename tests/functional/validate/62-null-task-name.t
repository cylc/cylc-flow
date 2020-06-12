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

# Fail on null task name!

. "$(dirname "$0")/test_header"

set_test_number 10

for GRAPH in 't1 => & t2' 't1 => t2 &' '& t1 => t2' 't1 & => t2' 't1 => => t2'
do
    cat >'suite.rc' <<__SUITE_RC__
[scheduling]
    [[graph]]
        R1 = ${GRAPH}
__SUITE_RC__
    run_fail "${TEST_NAME_BASE}" cylc validate 'suite.rc'
    grep_ok 'GraphParseError: null task name in graph: ' \
        "${TEST_NAME_BASE}.stderr"
done

exit
