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
# Test correct expansion of (FOO:finish-all & FOO:fail-any)
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" fam-expansion
SHOW_OUT="$PWD/show.out"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate --set="SHOW_OUT='$SHOW_OUT'" "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" \
    cylc play --debug --no-detach --set="SHOW_OUT='$SHOW_OUT'" "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
contains_ok "$SHOW_OUT" <<'__SHOW_DUMP__'
  ✓ (((1 | 0) & (3 | 2) & (5 | 4)) & (0 | 2 | 4))
  ✓ 	0 = 1/foo1 failed
  ⨯ 	1 = 1/foo1 succeeded
  ✓ 	2 = 1/foo2 failed
  ⨯ 	3 = 1/foo2 succeeded
  ✓ 	4 = 1/foo3 failed
  ⨯ 	5 = 1/foo3 succeeded
__SHOW_DUMP__
#-------------------------------------------------------------------------------
purge
