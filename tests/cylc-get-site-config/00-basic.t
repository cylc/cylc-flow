#!/bin/bash
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
# Test cylc-get-site-config
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 10
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-get-config"
run_ok "${TEST_NAME}.validate" cylc get-site-config
run_ok "${TEST_NAME}.print-run-dir" cylc get-site-config --print-run-dir
run_ok "${TEST_NAME}.print-site-dir" cylc get-site-config --print-site-dir
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-get-items"
run_ok "${TEST_NAME}.doc-section" cylc get-site-config --item='[documentation]'
run_ok "${TEST_NAME}.doc-section-python" \
    cylc get-site-config --item='[documentation]' -p
run_ok "${TEST_NAME}.multiple-secs" \
    cylc get-site-config --item='[documentation]' --item='[job platforms]'
run_ok "${TEST_NAME}.doc-entry" \
    cylc get-site-config --item='[documentation]online'
run_fail "${TEST_NAME}.non-existent" \
    cylc get-site-config --item='[this][doesnt]exist'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run-dir"
run_ok "${TEST_NAME}" cylc get-site-config --print-run-dir
#-------------------------------------------------------------------------------
VAL1="$(cylc get-site-config --item '[job platforms][localhost]use login shell')"
VAL2="$(cylc get-site-config | sed -n '/\[\[localhost\]\]/,$p' | \
    sed -n "0,/use login shell/s/^[ \t]*\(use login shell =.*\)/\1/p")"
run_ok "${TEST_NAME_BASE}-check-output" \
    test "use login shell = ${VAL1}" = "${VAL2}"
#-------------------------------------------------------------------------------
exit
