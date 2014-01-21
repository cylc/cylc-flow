#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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
#C: job script torture test and check jobscript is generated correctly
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE torture
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --reference-test --debug $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-foo-jobscript-match
run_ok $TEST_NAME cylc jobscript $SUITE_NAME foo.1
sed 's/\(export CYLC_.*=\).*/\1/g' $TEST_NAME.stdout > jobfile
echo "" >> jobfile
sed 's/##suitename##/'$SUITE_NAME'/' $TEST_SOURCE_DIR/torture/foo.ref-jobfile > reffile
cmp_ok jobfile reffile
purge_suite $SUITE_NAME
rm -rf $(cylc get-global-config --print-run-dir)/$SUITE_NAME-submit
