#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
# Test: family-OR logic pre-initial simplification bug (#1626).
. "$(dirname "$0")/test_header"
set_test_number 2

cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
    initial cycle point = 2000
    [[dependencies]]
        [[[T00]]]
            graph = """
                A
                B
                A[-PT24H]:fail-any | B[-PT24H]:fail-any => c"""
[runtime]
    [[A]]
    [[B]]
    [[a1]]
        inherit = A
    [[b1a, b2a, b3a]]
        inherit = B
    [[c]]
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${PWD}/suite.rc"

graph_suite "${PWD}/suite.rc" 'graph.plain'
cmp_ok 'graph.plain' - <<'__GRAPH__'
edge "A.20000101T0000+01" "c.20000102T0000+01" solid
edge "A.20000102T0000+01" "c.20000103T0000+01" solid
edge "B.20000101T0000+01" "c.20000102T0000+01" solid
edge "B.20000102T0000+01" "c.20000103T0000+01" solid
graph
node "A.20000101T0000+01" "A\n20000101T0000+01" unfilled doubleoctagon black
node "A.20000102T0000+01" "A\n20000102T0000+01" unfilled doubleoctagon black
node "A.20000103T0000+01" "A\n20000103T0000+01" unfilled doubleoctagon black
node "B.20000101T0000+01" "B\n20000101T0000+01" unfilled doubleoctagon black
node "B.20000102T0000+01" "B\n20000102T0000+01" unfilled doubleoctagon black
node "B.20000103T0000+01" "B\n20000103T0000+01" unfilled doubleoctagon black
node "c.20000101T0000+01" "c\n20000101T0000+01" unfilled box black
node "c.20000102T0000+01" "c\n20000102T0000+01" unfilled box black
node "c.20000103T0000+01" "c\n20000103T0000+01" unfilled box black
stop
__GRAPH__

exit
