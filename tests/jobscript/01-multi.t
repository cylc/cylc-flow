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
# Test jobscipt is being generated right for mult-inheritance cases
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 22
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE multi
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-foo
# check foo is correctly inheriting from FAM1
#   check pre-command and environment
run_ok $TEST_NAME cylc jobscript $SUITE_NAME foo.1
cp $TEST_NAME.stdout foo.jobfile
grep -A1 "PRE-COMMAND SCRIPTING" foo.jobfile > foo.pre_cmd
cmp_ok foo.pre $TEST_SOURCE_DIR/multi/foo.pre
run_ok $TEST_NAME.env grep 'MESSAGE="hello"' foo.jobfile
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-bar
# check bar is correctly inheriting from FAM1,FAM2
#   check pre, post and environment
run_ok $TEST_NAME cylc jobscript $SUITE_NAME bar.1
cp $TEST_NAME.stdout bar.jobfile
grep -A1 "PRE-COMMAND SCRIPTING" bar.jobfile > bar.pre_cmd
cmp_ok bar.pre_cmd $TEST_SOURCE_DIR/multi/bar.pre
grep -A1 "POST COMMAND SCRIPTING" bar.jobfile > bar.post_cmd
cmp_ok bar.post_cmd $TEST_SOURCE_DIR/multi/bar.post
run_ok $TEST_NAME.env grep 'MESSAGE="hello"' bar.jobfile
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-baz
# check baz is correctly overriding environment settings
run_ok $TEST_NAME cylc jobscript $SUITE_NAME baz.1
cp $TEST_NAME.stdout baz.jobfile
run_ok $TEST_NAME.env grep 'MESSAGE="baz"' baz.jobfile
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-qux
# check qux is correctly overriding pre-command scripting
run_ok $TEST_NAME cylc jobscript $SUITE_NAME qux.1
cp $TEST_NAME.stdout qux.jobfile
grep -A1 "PRE-COMMAND SCRIPTING" qux.jobfile > qux.pre_cmd
cmp_ok qux.pre_cmd $TEST_SOURCE_DIR/multi/qux.pre
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-bah
# check bah has correctly inherited pre-command scripting from FAM1,FAM3
run_ok $TEST_NAME cylc jobscript $SUITE_NAME bah.1
cp $TEST_NAME.stdout bah.jobfile
grep -A1 "PRE-COMMAND SCRIPTING" bah.jobfile > bah.pre_cmd
cmp_ok bah.pre_cmd $TEST_SOURCE_DIR/multi/bah.pre
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-hum
# check hum has correctly set post-command scripting
run_ok $TEST_NAME cylc jobscript $SUITE_NAME hum.1
cp $TEST_NAME.stdout hum.jobfile
grep -A1 "POST COMMAND SCRIPTING" hum.jobfile > hum.post_cmd
cmp_ok hum.post_cmd $TEST_SOURCE_DIR/multi/hum.post
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-bug
# check bug has correctly inherited command scripting from FAM4
run_ok $TEST_NAME cylc jobscript $SUITE_NAME bug.1
cp $TEST_NAME.stdout bug.jobfile
grep -A1 "TASK COMMAND SCRIPTING" bug.jobfile > bug.task_cmd
cmp_ok bug.task_cmd $TEST_SOURCE_DIR/multi/bug.cmd
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-reg
# check reg has correctly overridden command scripting
run_ok $TEST_NAME cylc jobscript $SUITE_NAME reg.1
cp $TEST_NAME.stdout reg.jobfile
grep -A1 "TASK COMMAND SCRIPTING" reg.jobfile > reg.task_cmd
cmp_ok reg.task_cmd $TEST_SOURCE_DIR/multi/reg.cmd
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-exp
# check exp has correctly inherited command scripting from FAM4,FAM5
run_ok $TEST_NAME cylc jobscript $SUITE_NAME exp.1
cp $TEST_NAME.stdout exp.jobfile
grep -A1 "TASK COMMAND SCRIPTING" exp.jobfile > exp.task_cmd
cmp_ok exp.task_cmd $TEST_SOURCE_DIR/multi/exp.cmd

purge_suite $SUITE_NAME
