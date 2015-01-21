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
# Test repeated item override and repeated graph string merge 
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 7
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE one
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-a
cylc get-config -i title $SUITE_NAME > a.txt
cmp_ok a.txt <<'__END'
the quick brown fox
__END
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-b
cylc get-config -i '[scheduling][dependencies]graph' $SUITE_NAME > b.txt
cmp_ok b.txt <<'__END'
foo => bar
bar => baz
__END
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-c
cylc get-config -i '[scheduling][dependencies][0]graph' $SUITE_NAME > c.txt
cmp_ok c.txt <<'__END'
cfoo => cbar
cbar => cbaz
dfoo => dbar
dbar => dbaz
__END
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-d
cylc get-config -i '[runtime][FOO]title' $SUITE_NAME > d.txt
cmp_ok d.txt <<'__END'
the quick brown fox
__END
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-e
cylc get-config -i '[runtime][FOO]description' $SUITE_NAME > e.txt
cmp_ok e.txt <<'__END'
jumped over the lazy dog
__END
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-f
cylc get-config -i '[runtime][FOO][environment]' $SUITE_NAME > f.txt
cmp_ok f.txt <<'__END'
VAR1 = the quick brown fox
__END
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
