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
# Test validation for a bad Jinja2 TemplateSyntaxError in a jinja include.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-val
run_fail "$TEST_NAME" cylc validate suite.rc
sed -i 's/^  File ".*", line/  File "FILE", line/g' "$TEST_NAME.stderr"
cmp_ok "$TEST_NAME.stderr" <<'__ERROR__'
Jinja2Error:
  File "FILE", line 3, in template
    {% end if %
TemplateSyntaxError: Encountered unknown tag 'end'. Jinja was looking for the following tags: 'elif' or 'else' or 'endif'. The innermost block that needs to be closed is 'if'.
__ERROR__
#-------------------------------------------------------------------------------
exit
