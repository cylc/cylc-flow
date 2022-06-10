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
# Test un-satisfiable dependencies are correctly identified in graphs
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 9
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    cycling mode = integer
    initial cycle point = 1
    [[graph]]
        # two un-satisfiable dependencies
        # (the inter-cycle deps are missaligned with the recurrences)
        1/P2 = a[-P2] => b
        2/P2 = b[-P2] => a
__FLOW_CONFIG__

#-------------------------------------------------------------------------------
# cylc validate should log warnings for the un-satisfiable dependencies
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
grep_ok "Detected un-satisfiable dependencies" "${TEST_NAME}.stderr"
grep_ok "1/a => 3/b" "${TEST_NAME}.stderr"
grep_ok "2/b => 4/a" "${TEST_NAME}.stderr"

#-------------------------------------------------------------------------------
# cylc graph should log warnings for the un-satisfiable dependencies
TEST_NAME="${TEST_NAME_BASE}-graph"
run_ok "${TEST_NAME}" cylc graph "${WORKFLOW_NAME}" 1 5 -o "${TEST_NAME}.dot"
grep_ok "Detected un-satisfiable dependencies" "${TEST_NAME}.stderr"
grep_ok "1/a => 3/b" "${TEST_NAME}.stderr"
grep_ok "2/b => 4/a" "${TEST_NAME}.stderr"
# cylc graph should render the un-satisfiable dependencies in a special way
# to set them apart
cmp_ok "${TEST_NAME}.dot" <<'__DOT__'
digraph {
  graph [fontname="sans" fontsize="25"]
  node [fontname="sans"]

  "1/a" [label="a\n1"]
  "1/b" [label="b\n1"]

  "2/a" [label="a\n2"]
  "2/b" [label="b\n2"]

  "3/a" [label="a\n3"]
  "3/b" [label="b\n3"]

  "4/a" [label="a\n4"]

  "5/b" [label="b\n5"]

  "1/a" [
    label="a
1"
    color="#888888"
    fontcolor="#888888"
  ]
  "1/a" -> "3/b" [color="#888888"]
  "3/a" [
    label="a
3"
    color="#888888"
    fontcolor="#888888"
  ]
  "3/a" -> "5/b" [color="#888888"]
  "2/b" [
    label="b
2"
    color="#888888"
    fontcolor="#888888"
  ]
  "2/b" -> "4/a" [color="#888888"]
}
__DOT__
purge
exit
