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
#
# "cylc set" proposal examples: 2 - Set off-flow prerequisites to prevent a new flow from stalling.
# https://cylc.github.io/cylc-admin/proposal-cylc-set.html#2-set-off-flow-prerequisites-to-prep-for-a-new-flow

. "$(dirname "$0")/test_header"
set_test_number 8

install_and_validate
reftest_run

grep_workflow_log_ok "${TEST_NAME_BASE}-ab" '1/a does not depend on "1/b_cold:succeeded"'
grep_workflow_log_ok "${TEST_NAME_BASE}-ac" '1/a does not depend on "1/c_cold:succeeded"'

grep_workflow_log_ok "${TEST_NAME_BASE}-ba" '1/b does not depend on "1/a_cold:succeeded"'
grep_workflow_log_ok "${TEST_NAME_BASE}-bc" '1/b does not depend on "1/c_cold:succeeded"'

grep_workflow_log_ok "${TEST_NAME_BASE}-ca" '1/c does not depend on "1/a_cold:succeeded"'
grep_workflow_log_ok "${TEST_NAME_BASE}-cb" '1/c does not depend on "1/b_cold:succeeded"'

purge
