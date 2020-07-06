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
# Test pre-initial cycling doesn't obliterate dependencies for tasks inserted
# before the warm start point
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" warm-insert-stall
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_fail "${TEST_NAME}" cylc run --debug --no-detach "${SUITE_NAME}" --warm 20100101T1800Z
#-------------------------------------------------------------------------------
grep_ok "WARNING - Unmet prerequisites for foo.20100101T1200Z:" \
    "${TEST_NAME_BASE}-run.stderr"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
