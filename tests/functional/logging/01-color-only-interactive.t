#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4

CYLCPATH=$(which cylc)

TEST_NAME="$TEST_NAME_BASE"
echo "${CYLCPATH} validate . --color=never"  > color-never
echo "${CYLCPATH} validate ."  > color-unspecified

run_fail "color never" bash color-never
run_fail "color off" bash -l color-unspecified
cmp_ok "color never.stderr" "color off.stderr"
grep_fail "\[m" "color never.stderr"

#-------------------------------------------------------------------------------
#purge
exit
