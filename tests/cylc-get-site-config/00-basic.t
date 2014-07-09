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
# Test cylc-get-site-config
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 9
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get-config
run_ok $TEST_NAME.validate cylc get-site-config
run_ok $TEST_NAME.print cylc get-site-config --print
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get-items
run_ok $TEST_NAME.doc-section cylc get-site-config --item='[documentation]'
run_ok $TEST_NAME.doc-section-python cylc get-site-config --item='[documentation]' -p
run_ok $TEST_NAME.multiple-secs cylc get-site-config --item='[documentation]' --item='[hosts]'
run_ok $TEST_NAME.doc-entry cylc get-site-config --item='[documentation][files]html index'
run_fail $TEST_NAME.non-existent cylc get-site-config --item='[this][doesnt]exist'
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run-dir
run_ok $TEST_NAME cylc get-site-config --print-run-dir
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-output
VAL1=$(cylc get-site-config --item '[hosts][localhost]use login shell')
VAL2=$(cylc get-site-config | sed -n '/\[\[localhost\]\]/,$p' | \
    sed -n "0,/use login shell/s/^[ \t]*\(use login shell =.*\)/\1/p")
echo use login shell = $VAL1 > testout
echo $VAL2 > refout
cmp_ok testout refout
#-------------------------------------------------------------------------------
