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

. "$(dirname "$0")/test_header"

set_test_number 15

install_workflow "${TEST_NAME_BASE}" integer

# run one cycle
TEST_NAME="${TEST_NAME_BASE}_run_1"
workflow_run_ok "${TEST_NAME}" cylc play --debug --no-detach --stopcp=1 "${WORKFLOW_NAME}"

# too many args
TEST_NAME="${TEST_NAME_BASE}_cl_error"
run_fail "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}-a" "${WORKFLOW_NAME}-b"

TEST_NAME="${TEST_NAME_BASE}_check_1_status"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}"

contains_ok "${TEST_NAME}.stdout" <<__END__
2/foo:waiting
1/foo:succeeded
1/bar:succeeded
__END__

TEST_NAME="${TEST_NAME_BASE}_check_1_outputs"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 --triggers "${WORKFLOW_NAME}"

contains_ok "${TEST_NAME}.stdout" <<__END__
1/foo:{'submitted': 'submitted', 'started': 'started', 'succeeded': 'succeeded', 'x': 'hello'}
2/foo:{}
1/bar:{'submitted': 'submitted', 'started': 'started', 'succeeded': 'succeeded'}
__END__

TEST_NAME="${TEST_NAME_BASE}_poll_fail"
run_fail "${TEST_NAME}" cylc workflow-state --max-polls=2 --interval=1 "${WORKFLOW_NAME}//2/foo:succeeded"

contains_ok "${TEST_NAME}.stderr" <<__END__
ERROR - failed after 2 polls
__END__

# finish the run
TEST_NAME="${TEST_NAME_BASE}_run_2"
workflow_run_ok "${TEST_NAME}" cylc play --debug --no-detach "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}_poll_succeed"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}//2/foo:succeeded"

contains_ok "${TEST_NAME}.stdout" <<__END__
2/foo:succeeded
__END__

TEST_NAME="${TEST_NAME_BASE}_int_offset"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}//1/foo:succeeded" --offset=P1

contains_ok "${TEST_NAME}.stdout" <<__END__
2/foo:succeeded
__END__

TEST_NAME="${TEST_NAME_BASE}_wildcard_offset"
run_fail "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}//*/foo:succeeded" --offset=P1

contains_ok "${TEST_NAME}.stderr" <<__END__
InputError: Cycle point "*" is not compatible with an offset.
__END__

purge
