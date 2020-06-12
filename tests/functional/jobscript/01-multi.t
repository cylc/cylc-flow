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
# Test jobscipt is being generated right for mult-inheritance cases
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 22
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" 'multi'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-foo"
# check foo is correctly inheriting from FAM1
#   check pre-command and environment
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" 'foo.1'
cp "${TEST_NAME}.stdout" 'foo.jobfile'
grep -A1 "# PRE-SCRIPT:" 'foo.jobfile' > 'foo.pre_cmd'
cmp_ok 'foo.pre' "${TEST_SOURCE_DIR}/multi/foo.pre"
grep_ok 'MESSAGE="hello"' 'foo.jobfile'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-bar"
# check bar is correctly inheriting from FAM1,FAM2
#   check pre, post and environment
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" 'bar.1'
cp "${TEST_NAME}.stdout" 'bar.jobfile'
grep -A1 "# PRE-SCRIPT:" 'bar.jobfile' > 'bar.pre_cmd'
cmp_ok 'bar.pre_cmd' "${TEST_SOURCE_DIR}/multi/bar.pre"
grep -A1 "# POST-SCRIPT:" 'bar.jobfile' > 'bar.post_cmd'
cmp_ok 'bar.post_cmd' "${TEST_SOURCE_DIR}/multi/bar.post"
grep_ok 'MESSAGE="hello"' 'bar.jobfile'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-baz"
# check baz is correctly overriding environment settings
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" 'baz.1'
cp "${TEST_NAME}.stdout" 'baz.jobfile'
grep_ok 'MESSAGE="baz"' 'baz.jobfile'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-qux"
# check qux is correctly overriding pre-script
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" 'qux.1'
cp "${TEST_NAME}.stdout" 'qux.jobfile'
grep -A1 "# PRE-SCRIPT:" 'qux.jobfile' > 'qux.pre_cmd'
cmp_ok 'qux.pre_cmd' "${TEST_SOURCE_DIR}/multi/qux.pre"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-bah"
# check bah has correctly inherited pre-script from FAM1,FAM3
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" 'bah.1'
cp "${TEST_NAME}.stdout" 'bah.jobfile'
grep -A1 "# PRE-SCRIPT:" 'bah.jobfile' > 'bah.pre_cmd'
cmp_ok 'bah.pre_cmd' "${TEST_SOURCE_DIR}/multi/bah.pre"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-hum"
# check hum has correctly set post-script
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" 'hum.1'
cp "${TEST_NAME}.stdout" 'hum.jobfile'
grep -A1 "# POST-SCRIPT:" 'hum.jobfile' > 'hum.post_cmd'
cmp_ok 'hum.post_cmd' "${TEST_SOURCE_DIR}/multi/hum.post"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-bug"
# check bug has correctly inherited script from FAM4
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" 'bug.1'
cp "${TEST_NAME}.stdout" 'bug.jobfile'
grep -A1 "# SCRIPT:" 'bug.jobfile' > 'bug.task_cmd'
cmp_ok 'bug.task_cmd' "${TEST_SOURCE_DIR}/multi/bug.cmd"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-reg"
# check reg has correctly overridden script
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" 'reg.1'
cp "${TEST_NAME}.stdout" 'reg.jobfile'
grep -A1 "# SCRIPT:" 'reg.jobfile' > 'reg.task_cmd'
cmp_ok 'reg.task_cmd' "${TEST_SOURCE_DIR}/multi/reg.cmd"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-exp"
# check exp has correctly inherited script from FAM4,FAM5
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" 'exp.1'
cp "${TEST_NAME}.stdout" 'exp.jobfile'
grep -A1 "# SCRIPT:" 'exp.jobfile' > 'exp.task_cmd'
cmp_ok 'exp.task_cmd' "${TEST_SOURCE_DIR}/multi/exp.cmd"

purge_suite "${SUITE_NAME}"
