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
# Test "cylc get-config" on a cycling suite, result should validate.
. "$(dirname "$0")/test_header"

set_test_number 2

init_suite "${TEST_NAME_BASE}" "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/suite.rc"

run_ok "${TEST_NAME_BASE}" cylc get-config "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate --strict "${TEST_NAME_BASE}.stdout"
purge_suite "${SUITE_NAME}"
exit
