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
# job script torture test and check jobscript is generated correctly
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
CYLC_CONF_PATH= suite_run_ok $TEST_NAME \
    cylc run --reference-test --debug $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-foo-jobscript-match
CYLC_CONF_PATH= run_ok $TEST_NAME cylc jobscript $SUITE_NAME foo.1
sed 's/\(export CYLC_.*=\).*/\1/g' $TEST_NAME.stdout >jobfile
sed 's/##suitename##/'$SUITE_NAME'/' \
    $TEST_SOURCE_DIR/$TEST_NAME_BASE/foo.ref-jobfile >reffile
cmp_ok jobfile reffile
purge_suite $SUITE_NAME
