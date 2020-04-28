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
# Test "cylc jobscript" when we have bad syntax in "script" value.
. "$(dirname "${0}")/test_header"
#-------------------------------------------------------------------------------
set_test_number 8
#-------------------------------------------------------------------------------
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[scheduling]
    [[graph]]
        R1 = foo
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
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = true
        pre-script = """
# stuff 1
# stuff 2
# stuff 3
"""
__SUITE_RC__

TEST_NAME="${TEST_NAME_BASE}"-comment-only
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" 'foo.1'
grep_ok 'cylc__job__inst__script' "${TEST_NAME}.stdout"
run_fail "${TEST_NAME}.stdout.pre_script" \
    grep -F -q 'cylc__job__inst__pre_script' "${TEST_NAME}.stdout"
purge_suite "${SUITE_NAME}"
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
TEST_NAME="${TEST_NAME_BASE}-advanced-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
TEST_NAME="${TEST_NAME_BASE}-advanced-run"
run_ok "${TEST_NAME}" cylc run "${SUITE_NAME}" --reference-test --debug --no-detach
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
