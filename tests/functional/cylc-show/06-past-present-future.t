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

set_test_number 4

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

# play workflow, shutdown and restart at task c so that task b (in n=1) gets
# loaded from the DB.
cylc play "${WORKFLOW_NAME}"
cylc workflow-state -t c -p 1 --max-polls=10 --interval=2 --status=running \
   ${WORKFLOW_NAME} 
cylc stop --now --max-polls=10 --interval=2 ${WORKFLOW_NAME}
cylc workflow-state -t c -p 1 --max-polls=10 --interval=2 --status=running \
   ${WORKFLOW_NAME} 
cylc play ${WORKFLOW_NAME}
cylc show ${WORKFLOW_NAME}//1/b > show.past
cylc show ${WORKFLOW_NAME}//1/c > show.present
cylc show ${WORKFLOW_NAME}//1/d > show.future
cylc stop --now --max-polls=10 --interval=2 ${WORKFLOW_NAME}

TEST_NAME=${TEST_NAME_BASE}-show.past
contains_ok show.past <<__END__
prerequisites: (n/a for past tasks)
__END__

TEST_NAME=${TEST_NAME_BASE}-show.present
contains_ok show.present <<__END__
prerequisites: ('-': not satisfied)
  + 1/b succeeded
__END__

TEST_NAME=${TEST_NAME_BASE}-show.future
contains_ok show.future <<__END__
prerequisites: ('-': not satisfied)
  - 1/c succeeded
__END__

purge
