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
# Test cylc-get-site-config
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 9
export CYLC_CONF_PATH=
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get-config
run_ok $TEST_NAME.validate cylc get-site-config
run_ok $TEST_NAME.print cylc get-site-config --print
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get-items
run_ok $TEST_NAME.doc-section cylc get-site-config --item='[documentation]'
run_ok $TEST_NAME.doc-section-python \
    cylc get-site-config --item='[documentation]' -p
run_ok $TEST_NAME.multiple-secs \
    cylc get-site-config --item='[documentation]' --item='[hosts]'
run_ok $TEST_NAME.doc-entry \
    cylc get-site-config --item='[documentation][files]html index'
run_fail $TEST_NAME.non-existent \
    cylc get-site-config --item='[this][doesnt]exist'
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
exit
