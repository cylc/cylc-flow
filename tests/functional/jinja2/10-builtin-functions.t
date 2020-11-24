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
# jinja2 test cylc-provided functions.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 5
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}"-pass
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}" \
    -s 'FOO="True"' \
    -s 'ANSWER="42"'
TEST_NAME="${TEST_NAME_BASE}"-fail-assert
run_fail "${TEST_NAME}" cylc validate "${SUITE_NAME}" \
    -s 'FOO="True"' \
    -s 'ANSWER="43"'
grep_ok 'Jinja2 Assertion Error: Universal' "${TEST_NAME}.stderr"
TEST_NAME="${TEST_NAME_BASE}"-fail-raise
run_fail "${TEST_NAME}" cylc validate "${SUITE_NAME}" -s 'ANSWER="42"'
grep_ok 'Jinja2 Error: FOO must be defined' "${TEST_NAME}.stderr"
#-------------------------------------------------------------------------------
purge
