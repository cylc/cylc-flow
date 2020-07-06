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
# Test host selection
. "$(dirname "$0")/test_header"
set_test_remote
set_test_number 3

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"

N_HOST_SELECT_CMDS="$(find "${SUITE_RUN_DIR}" -name 'host-select-*' | wc -l)"
run_ok "${TEST_NAME_BASE}-n-host-select-cmds" test "${N_HOST_SELECT_CMDS}" -eq 1
purge_suite_remote "${CYLC_TEST_HOST}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
