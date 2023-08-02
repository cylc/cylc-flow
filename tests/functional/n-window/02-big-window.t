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

# Test large window size using graphql and find tasks in window.
# This is helpful with coverage by using most the no-rewalk mechanics.

. "$(dirname "$0")/test_header"

set_test_number 5

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

# First run: task c shuts the scheduler down then fails.
TEST_NAME="${TEST_NAME_BASE}-run"
# 'a => b => . . . f => g => h', 'a' sets window size to 5,
# 'b => i => j => f', 'c' finds 'a', 'j', 'h'
workflow_run_ok "${TEST_NAME}" cylc play --no-detach --debug "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}-show-a.past"
contains_ok "$WORKFLOW_RUN_DIR/show-a.txt" <<__END__
state: succeeded
prerequisites: (None)
__END__

TEST_NAME="${TEST_NAME_BASE}-show-j.parallel"
contains_ok "${WORKFLOW_RUN_DIR}/show-j.txt" <<__END__
state: waiting
prerequisites: ('-': not satisfied)
  - 1/i succeeded
__END__

TEST_NAME="${TEST_NAME_BASE}-show-h.future"
contains_ok "${WORKFLOW_RUN_DIR}/show-h.txt" <<__END__
state: waiting
prerequisites: ('-': not satisfied)
  - 1/g succeeded
__END__

purge
