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
# Test validation for a bad no-line-number Jinja2 error.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-val
run_fail "$TEST_NAME" cylc validate suite.rc
sed -i 's/^  File ".*/  File "FILE", line NN, in ROUTINE/g' "$TEST_NAME.stderr"
cmp_ok "$TEST_NAME.stderr" <<'__ERROR__'
Jinja2Error:
  File "FILE", line NN, in ROUTINE
    raise TemplateNotFound(template)
TemplateNotFound: suite-foo.rc
__ERROR__
#-------------------------------------------------------------------------------
exit
