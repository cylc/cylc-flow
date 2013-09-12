#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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
#C: Test jobscipt is being generated right for mult-inheritance cases
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 13
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE multi
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-foo
# check foo is correctly inheriting from FAM1
#   check pre-command and environment
run_ok echo "pre"
run_ok echo "env"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-bar
# check bar is correctly inheriting from FAM1,FAM2
#   check pre, post and environment
run_ok echo "pre"
run_ok echo "post"
run_ok echo "env"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-baz
# check baz is correctly overriding environment settings
run_ok echo "env"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-qux
# check qux is correctly overriding pre-command scripting
run_ok echo "pre"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-bah
# check bah has correctly inherited pre-command scripting from FAM1,FAM3
run_ok echo "pre"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-hum
# check hum has correctly set post-command scripting
run_ok echo "post"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-bug
# check bug has correctly inherited command scripting from FAM4
run_ok echo "cmd"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-reg
# check reg has correctly overridden command scripting
run_ok echo "cmd"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-exp
# check reg has correctly inherited command scripting from FAM4,FAM5
run_ok echo "cmd"

purge_suite $SUITE_NAME
