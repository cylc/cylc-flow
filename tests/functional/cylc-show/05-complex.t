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
# Test cylc show for a basic task.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
TEST_SHOW_OUTPUT_PATH="$PWD/${TEST_NAME_BASE}-show.stdout"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate \
   --set="TEST_OUTPUT_PATH='$TEST_SHOW_OUTPUT_PATH'"  "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
run_ok "${TEST_NAME}" cylc play \
   --no-detach --set="TEST_OUTPUT_PATH='$TEST_SHOW_OUTPUT_PATH'" "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-show"
contains_ok "${TEST_SHOW_OUTPUT_PATH}" << '__OUT__'
title: (not given)
description: (not given)
URL: (not given)
state: running
prerequisites: ('⨯': not satisfied)
  ✓ 1 & 2 & (3 | (4 & 5)) & 0
  ✓ 	0 = 19991231T0000Z/f succeeded
  ✓ 	1 = 20000101T0000Z/a succeeded
  ✓ 	2 = 20000101T0000Z/b succeeded
  ✓ 	3 = 20000101T0000Z/c succeeded
  ✓ 	4 = 20000101T0000Z/d succeeded
  ✓ 	5 = 20000101T0000Z/e succeeded
outputs: ('⨯': not completed)
  ⨯ 20000101T0000Z/f expired
  ✓ 20000101T0000Z/f submitted
  ⨯ 20000101T0000Z/f submit-failed
  ✓ 20000101T0000Z/f started
  ⨯ 20000101T0000Z/f succeeded
  ⨯ 20000101T0000Z/f failed
output completion: incomplete
  ⨯ ⦙  succeeded
19991231T0000Z/f succeeded
20000101T0000Z/a succeeded
20000101T0000Z/b succeeded
20000101T0000Z/c succeeded
20000101T0000Z/d succeeded
20000101T0000Z/e succeeded
title: (not given)
description: (not given)
URL: (not given)
state: running
prerequisites: ('⨯': not satisfied)
  ✓ 1 & 2 & (3 | (4 & 5)) & 0
  ✓ 	0 = 20000101T0000Z/f succeeded
  ✓ 	1 = 20000102T0000Z/a succeeded
  ✓ 	2 = 20000102T0000Z/b succeeded
  ✓ 	3 = 20000102T0000Z/c succeeded
  ✓ 	4 = 20000102T0000Z/d succeeded
  ✓ 	5 = 20000102T0000Z/e succeeded
outputs: ('⨯': not completed)
  ⨯ 20000102T0000Z/f expired
  ✓ 20000102T0000Z/f submitted
  ⨯ 20000102T0000Z/f submit-failed
  ✓ 20000102T0000Z/f started
  ⨯ 20000102T0000Z/f succeeded
  ⨯ 20000102T0000Z/f failed
output completion: incomplete
  ⨯ ⦙  succeeded
20000101T0000Z/f succeeded
20000102T0000Z/a succeeded
20000102T0000Z/b succeeded
20000102T0000Z/c succeeded
20000102T0000Z/d succeeded
20000102T0000Z/e succeeded
__OUT__
#-------------------------------------------------------------------------------
purge
