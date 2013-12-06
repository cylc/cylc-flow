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
# Test environment filtering
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 5
#-------------------------------------------------------------------------------
# a test suite that uses environment filtering:
init_suite $TEST_NAME_BASE <<'__SUITERC__'
[scheduling]
    [[dependencies]]
        graph = "foo & bar"
[runtime]
    [[root]]
        [[[environment]]]
            FOO = foo
            BAR = bar
            BAZ = baz
    [[foo]]
        environment filter = FOO, BAR
        [[[environment]]]
            QUX = qux
    [[bar]]
        [[[environment]]]
            QUX = qux
__SUITERC__
#-------------------------------------------------------------------------------
# check validation
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc val $SUITE_NAME
#-------------------------------------------------------------------------------
# check that get-config retrieves only the filtered environment
TEST_NAME=$TEST_NAME_BASE-get-config
run_ok $TEST_NAME cylc get-config --item='[runtime][foo]environment' $SUITE_NAME
cmp_ok $TEST_NAME.stdout - <<__OUT__
FOO = foo
BAR = bar
__OUT__
cmp_ok $TEST_NAME.stderr - </dev/null
#-------------------------------------------------------------------------------
# check that the task job script contains only the filtered environment
TEST_NAME=$TEST_NAME_BASE-jobscript
cylc jobscript foo foo.1 2> /dev/null | \
    perl -0777 -ne 'print $1 if /# TASK RUNTIME ENVIRONMENT:\n(.*?)export/s' > foo.stdout
cmp_ok foo.stdout - <<__OUT__
FOO="foo"
BAR="bar"
__OUT__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME

