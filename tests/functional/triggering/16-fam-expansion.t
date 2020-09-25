#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
# Test correct expansion of (FOO:finish-all & FOO:fail-any)
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" fam-expansion
SHOW_OUT="$PWD/show.out"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate --set="SHOW_OUT=$SHOW_OUT" "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" \
    cylc run --debug --no-detach --set="SHOW_OUT=$SHOW_OUT" "${SUITE_NAME}"
#-------------------------------------------------------------------------------
contains_ok "$SHOW_OUT" <<'__SHOW_DUMP__'
  + (((1 | 0) & (3 | 2) & (5 | 4)) & (0 | 2 | 4))
  + 	0 = foo1.1 failed
  - 	1 = foo1.1 succeeded
  + 	2 = foo2.1 failed
  - 	3 = foo2.1 succeeded
  + 	4 = foo3.1 failed
  - 	5 = foo3.1 succeeded
__SHOW_DUMP__
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
