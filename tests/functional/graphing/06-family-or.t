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
# Test: family-OR logic pre-initial simplification bug (#1626).
. "$(dirname "$0")/test_header"
set_test_number 3

cat >'flow.cylc' <<'__FLOW_CONFIG__'
[scheduler]
    UTC mode = True
[scheduling]
    initial cycle point = 2000
    [[graph]]
        T00 = """
            A?
            B?
            A[-PT24H]:fail-any? | B[-PT24H]:fail-any? => c
        """
[runtime]
    [[A]]
    [[B]]
    [[a1]]
        inherit = A
    [[b1a, b2a, b3a]]
        inherit = B
    [[c]]
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${PWD}"

graph_workflow "${PWD}" "graph.plain" \
   -g A -g B -g X 20000101T0000Z 20000103T0000Z
cmp_ok 'graph.plain' - <<'__GRAPH__'
edge "20000101T0000Z/A" "20000102T0000Z/c"
edge "20000101T0000Z/B" "20000102T0000Z/c"
edge "20000102T0000Z/A" "20000103T0000Z/c"
edge "20000102T0000Z/B" "20000103T0000Z/c"
graph
node "20000101T0000Z/A" "A\n20000101T0000Z"
node "20000101T0000Z/B" "B\n20000101T0000Z"
node "20000101T0000Z/c" "c\n20000101T0000Z"
node "20000102T0000Z/A" "A\n20000102T0000Z"
node "20000102T0000Z/B" "B\n20000102T0000Z"
node "20000102T0000Z/c" "c\n20000102T0000Z"
node "20000103T0000Z/A" "A\n20000103T0000Z"
node "20000103T0000Z/B" "B\n20000103T0000Z"
node "20000103T0000Z/c" "c\n20000103T0000Z"
stop
__GRAPH__

grep_ok "Ignoring undefined family X" "graph.plain.err" 

exit
