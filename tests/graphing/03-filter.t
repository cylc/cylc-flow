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
# Test filtering out graph nodes, preserving edge structure.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate "$SUITE_NAME"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-as-is
graph_suite $SUITE_NAME graph.plain.test.orig
cmp_ok graph.plain.test.orig $TEST_SOURCE_DIR/$TEST_NAME_BASE/graph.plain.ref.orig
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-filtered
graph_suite $SUITE_NAME graph.plain.test.filtered \
    --filter='^banana.1$' --filter='^blackberry.1$' --filter=lueberry \
    --filter='^cherry.1$' --filter='^date.1$' --filter='^durian.1$' \
    --filter='^elderberry.1$' --filter='^grape.1$' --filter='^coconut.1$' \
    --filter='^breadfruit.1$'
cmp_ok graph.plain.test.filtered $TEST_SOURCE_DIR/$TEST_NAME_BASE/graph.plain.ref.filtered
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
