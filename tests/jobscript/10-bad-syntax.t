#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
# Test "cylc jobscript" when we have bad syntax in "script" value.
. "$(dirname "${0}")/test_header"
#-------------------------------------------------------------------------------
set_test_number 5
#-------------------------------------------------------------------------------
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[scheduling]
    [[dependencies]]
        graph = foo
[runtime]
    [[foo]]
        script = fi
__SUITE_RC__

TEST_NAME="${TEST_NAME_BASE}"-simple
run_fail "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" 'foo.1'
cmp_ok "${TEST_NAME}.stdout" <'/dev/null'
contains_ok "${TEST_NAME}.stderr" <<__ERR__
ERROR: no jobscript generated
__ERR__
purge_suite "${SUITE_NAME}"
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
TEST_NAME="${TEST_NAME_BASE}-advanced-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
TEST_NAME="${TEST_NAME_BASE}-advanced-run"
run_ok "${TEST_NAME}" cylc run "${SUITE_NAME}" --reference-test --debug
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
