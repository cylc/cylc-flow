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
[[m1]]
   inherit = FAMILY
   [[[environment]]]
      FOO = foo
[[m3]]
   inherit = FAMILY
   [[[environment]]]
      FOO = foo
[[FAMILY]]
[[m2]]
   inherit = FAMILY
   [[[environment]]]
      FOO = bar
__DONE__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
exit
