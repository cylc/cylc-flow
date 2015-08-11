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
# Test that members of namespace lists [[n1,n2,...]] are inserted into the
# [runtime] ordered dict in the correct order. If just appended, they break
# repeat-section override for the member.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok "$TEST_NAME" cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get-config
cylc get-config --sparse -i runtime $SUITE_NAME > runtime.out
cmp_ok runtime.out <<'__DONE__'
[[root]]
[[FAMILY]]
[[m1]]
   inherit = FAMILY
   [[[environment]]]
      FOO = foo
[[m2]]
   inherit = FAMILY
   [[[environment]]]
      FOO = bar
[[m3]]
   inherit = FAMILY
   [[[environment]]]
      FOO = foo
__DONE__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
exit
