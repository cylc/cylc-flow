#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
# Test validation for a filter Jinja2 error with no line number.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-val
run_fail "$TEST_NAME" cylc validate suite.rc
# Filter Python version specific output, e.g.:
#   File "/usr/lib/python2.6/site-packages/jinja2/filters.py", line 183, in do_dictsort
sed -i '/File.*in do_dictsort/d' "$TEST_NAME.stderr"
cmp_ok "$TEST_NAME.stderr" <<'__ERROR__'
Jinja2Error:
    raise FilterArgumentError('You can only sort by either '
FilterArgumentError: You can only sort by either "key" or "value"
__ERROR__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
exit
