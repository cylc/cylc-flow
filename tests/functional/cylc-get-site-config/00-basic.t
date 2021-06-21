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
# Test getting the global config
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-config"
run_ok "${TEST_NAME}.validate" cylc config
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-get-items"
run_fail "${TEST_NAME}.non-existent" \
    cylc config --item='[this][doesnt]exist'
#-------------------------------------------------------------------------------
VAL1="$(cylc config -d --item '[platforms][localhost]use login shell')"
VAL2="$(cylc config -d | sed -n '/\[\[localhost\]\]/,$p' | \
    sed -n "0,/use login shell/s/^[ \t]*\(use login shell =.*\)/\1/p")"
run_ok "${TEST_NAME_BASE}-check-output" \
    test "use login shell = ${VAL1}" = "${VAL2}"
#-------------------------------------------------------------------------------
exit
