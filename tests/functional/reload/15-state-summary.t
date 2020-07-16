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
# Test that the state summary updates immediately when a reload finishes.
# (SoD: the original test contrived to get a succeeded and a failed task in the
# pool, and no active tasks. That's not possible under SoD, and it seems to me
# a trivial held suite should do to test that the state summary updates after a
# reload when nothing else is happening).  
# See https://github.com/cylc/cylc-flow/pull/1756
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[scheduling]
   [[graph]]
      R1 = foo
[runtime]
   [[foo]]
      script = true
__SUITERC__
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
# Suite runs and shuts down with a failed task.
cylc run --hold "${SUITE_NAME}" > /dev/null 2>&1
sleep 5
cylc reload "${SUITE_NAME}"
sleep 5
cylc dump "${SUITE_NAME}" > dump.out
TEST_NAME=${TEST_NAME_BASE}-grep
# State summary should not say "reloading = True"
grep_ok "reloading=False" dump.out
#-------------------------------------------------------------------------------
cylc stop --max-polls=10 --interval=2 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
