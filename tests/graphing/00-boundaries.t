#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test "[visualization]number of cycles" for a suite with two different cycling
# intervals.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate "$SUITE_NAME"
#-------------------------------------------------------------------------------
# Two tests:
for POINT in 20140808T00 20140808T06; do
    TEST_NAME=$TEST_NAME_BASE-graph-$POINT
    graph_suite $SUITE_NAME $POINT.graph.plain $POINT
    cmp_ok $POINT.graph.plain \
        $TEST_SOURCE_DIR/$TEST_NAME_BASE/$POINT.graph.plain.ref
done
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
