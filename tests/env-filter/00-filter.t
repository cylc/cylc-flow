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
# Test environment filtering
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 17 
#-------------------------------------------------------------------------------
# a test suite that uses environment filtering:
init_suite $TEST_NAME_BASE <<'__SUITERC__'
[scheduling]
    [[dependencies]]
        graph = "foo & bar & baz & qux"
[runtime]
    [[root]]
        [[[environment]]]
            FOO = foo
            BAR = bar
            BAZ = baz
    [[foo]]
        [[[environment filter]]]
            include = FOO, BAR
        [[[environment]]]
            QUX = qux
    [[bar]]
        [[[environment filter]]]
            include = FOO, BAR
            exclude = FOO
    [[baz]]
        [[[environment filter]]]
            exclude = FOO, BAR
        [[[environment]]]
            QUX = qux
    [[qux]]
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

run_ok $TEST_NAME cylc get-config --item='[runtime][bar]environment' $SUITE_NAME
cmp_ok $TEST_NAME.stdout - <<__OUT__
BAR = bar
__OUT__
cmp_ok $TEST_NAME.stderr - </dev/null

run_ok $TEST_NAME cylc get-config --item='[runtime][baz]environment' $SUITE_NAME
cmp_ok $TEST_NAME.stdout - <<__OUT__
BAZ = baz
QUX = qux
__OUT__
cmp_ok $TEST_NAME.stderr - </dev/null

run_ok $TEST_NAME cylc get-config --item='[runtime][qux]environment' $SUITE_NAME
cmp_ok $TEST_NAME.stdout - <<__OUT__
FOO = foo
BAR = bar
BAZ = baz
QUX = qux
__OUT__
cmp_ok $TEST_NAME.stderr - </dev/null

#-------------------------------------------------------------------------------
# check that task job scripts contain only the filtered environment
TEST_NAME=$TEST_NAME_BASE-jobscript

cylc jobscript $SUITE_NAME foo.1 2> /dev/null | \
    perl -0777 -ne 'print $1 if /# TASK RUNTIME ENVIRONMENT:\n(.*?)export/s' > $SUITE_NAME.stdout
cmp_ok $SUITE_NAME.stdout - <<__OUT__
FOO="foo"
BAR="bar"
__OUT__

cylc jobscript $SUITE_NAME bar.1 2> /dev/null | \
    perl -0777 -ne 'print $1 if /# TASK RUNTIME ENVIRONMENT:\n(.*?)export/s' > $SUITE_NAME.stdout
cmp_ok $SUITE_NAME.stdout - <<__OUT__
BAR="bar"
__OUT__

cylc jobscript $SUITE_NAME baz.1 2> /dev/null | \
    perl -0777 -ne 'print $1 if /# TASK RUNTIME ENVIRONMENT:\n(.*?)export/s' > $SUITE_NAME.stdout
cmp_ok $SUITE_NAME.stdout - <<__OUT__
BAZ="baz"
QUX="qux"
__OUT__

cylc jobscript $SUITE_NAME qux.1 2> /dev/null | \
    perl -0777 -ne 'print $1 if /# TASK RUNTIME ENVIRONMENT:\n(.*?)export/s' > $SUITE_NAME.stdout
cmp_ok $SUITE_NAME.stdout - <<__OUT__
FOO="foo"
BAR="bar"
BAZ="baz"
QUX="qux"
__OUT__

#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
