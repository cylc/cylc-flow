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

# Test cylc-show prerequisites for past, future, and present tasks.

. "$(dirname "$0")/test_header"

set_test_number 6

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

# First run: task c shuts the scheduler down then fails.
TEST_NAME="${TEST_NAME_BASE}-run-1"
workflow_run_ok "${TEST_NAME}" cylc play --no-detach --debug "${WORKFLOW_NAME}"

# Restart: task kick-c triggers off of c's failure, and re-triggers c.
# Then, c runs `cylc show` on tasks b, c, and d.
TEST_NAME="${TEST_NAME_BASE}-run-2"
workflow_run_ok "${TEST_NAME}" cylc play --no-detach --debug "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}-show.past"
contains_ok "$WORKFLOW_RUN_DIR/show-b.txt" <<__END__
state: succeeded
prerequisites: (n/a for past tasks)
__END__

TEST_NAME="${TEST_NAME_BASE}-show.present"
contains_ok "${WORKFLOW_RUN_DIR}/show-c.txt" <<__END__
state: running
prerequisites: ('⨯': not satisfied)
  ✓ 1/b succeeded
__END__

TEST_NAME="${TEST_NAME_BASE}-show.future"
contains_ok "${WORKFLOW_RUN_DIR}/show-d.txt" <<__END__
state: waiting
prerequisites: ('⨯': not satisfied)
  ⨯ 1/c succeeded
__END__

purge
