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
# Test intercycle dependencies, local time.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
CHOSEN_SUITE=$(basename $0 | sed "s/^.*-\(.*\)\.t/\1/g")
install_suite $TEST_NAME_BASE $CHOSEN_SUITE
CURRENT_TZ_UTC_OFFSET=$(date +%z)
if [[ $CURRENT_TZ_UTC_OFFSET == '+0000' ]]; then
    CURRENT_TZ_UTC_OFFSET="Z"
else
    CURRENT_TZ_UTC_OFFSET=${CURRENT_TZ_UTC_OFFSET%00}
fi
sed -i "s/Z/$CURRENT_TZ_UTC_OFFSET/g" reference.log
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-graph
graph_suite "$SUITE_NAME" "$SUITE_NAME.graph.plain"
sed "s/Z/$CURRENT_TZ_UTC_OFFSET/g" \
    "$TEST_SOURCE_DIR/$CHOSEN_SUITE/graph.plain.ref" > graph.plain.local.ref
cmp_ok "$SUITE_NAME.graph.plain" graph.plain.local.ref
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --reference-test --debug $SUITE_NAME
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
