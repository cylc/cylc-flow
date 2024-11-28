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
# Functional test of the cylc-list command
# (see integration tests for more comprehensive tests)

. "$(dirname "$0")/test_header"
set_test_number 4


cat > flow.cylc <<__FLOW__
[scheduling]
    [[graph]]
        R1 = c
[runtime]
    [[A]]
        [[[meta]]]
            title = Aaa
    [[B]]
        inherit = A
        [[[meta]]]
            title = Bbb
    [[c]]
        inherit = B
        [[[meta]]]
            title = Ccc
__FLOW__


# test signals on a detached scheduler
TEST_NAME="${TEST_NAME_BASE}-list"
run_ok "$TEST_NAME" cylc list '.' --all-namespaces --with-titles
cmp_ok "${TEST_NAME}.stdout" << __HERE__
A     Aaa
B     Bbb
c     Ccc
root  
__HERE__

TEST_NAME="${TEST_NAME_BASE}-tree"
run_ok "$TEST_NAME" cylc list '.' --tree --with-titles
cmp_ok "${TEST_NAME}.stdout" << '__HERE__'
root     
 `-A     
   `-B   
     `-c Ccc
__HERE__
