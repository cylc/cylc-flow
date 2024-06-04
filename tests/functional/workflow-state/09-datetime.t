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

set_test_number 24

install_workflow "${TEST_NAME_BASE}" datetime

# run one cycle
TEST_NAME="${TEST_NAME_BASE}_run_1"
workflow_run_ok "${TEST_NAME}" cylc play --debug --no-detach --stopcp=2051 "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}_check_1_status"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}"

contains_ok "${TEST_NAME}.stdout" <<__END__
2052/foo:waiting
2051/foo:succeeded
2051/bar:succeeded
__END__

TEST_NAME="${TEST_NAME_BASE}_check_1_status_old_fmt"
run_ok "${TEST_NAME}" cylc workflow-state --old-format --max-polls=1 "${WORKFLOW_NAME}"

contains_ok "${TEST_NAME}.stdout" <<__END__
foo, 2052, waiting
foo, 2051, succeeded
bar, 2051, succeeded
__END__

TEST_NAME="${TEST_NAME_BASE}_check_1_outputs"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 --output "${WORKFLOW_NAME}"

contains_ok "${TEST_NAME}.stdout" <<__END__
2051/foo:{'submitted': 'submitted', 'started': 'started', 'succeeded': 'succeeded', 'x': 'hello'}
2052/foo:{}
2051/bar:{'submitted': 'submitted', 'started': 'started', 'succeeded': 'succeeded'}
__END__

TEST_NAME="${TEST_NAME_BASE}_poll_fail"
run_fail "${TEST_NAME}" cylc workflow-state --max-polls=2 --interval=1 "${WORKFLOW_NAME}//2052/foo:succeeded"

contains_ok "${TEST_NAME}.stderr" <<__END__
ERROR: condition not satisfied after 2 polls
__END__

# finish the run
TEST_NAME="${TEST_NAME_BASE}_run_2"
workflow_run_ok "${TEST_NAME}" cylc play --debug --no-detach "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}_check_1_status_2"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}"

contains_ok "${TEST_NAME}.stdout" <<__END__
2051/foo:succeeded
2052/foo:succeeded
2051/bar:succeeded
2052/bar:succeeded
2052/foo:succeeded(flows=2)
2052/bar:succeeded(flows=2)
__END__

TEST_NAME="${TEST_NAME_BASE}_check_1_status_3"
run_ok "${TEST_NAME}" cylc workflow-state --flow=2 --max-polls=1 "${WORKFLOW_NAME}"

contains_ok "${TEST_NAME}.stdout" <<__END__
2052/foo:succeeded(flows=2)
2052/bar:succeeded(flows=2)
__END__

TEST_NAME="${TEST_NAME_BASE}_check_1_wildcard"
run_ok "${TEST_NAME}" cylc workflow-state --flow=1 --max-polls=1 "${WORKFLOW_NAME}//*/foo"

contains_ok "${TEST_NAME}.stdout" <<__END__
2051/foo:succeeded
__END__

TEST_NAME="${TEST_NAME_BASE}_poll_succeed"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}//2052/foo:succeeded"

contains_ok "${TEST_NAME}.stdout" <<__END__
2052/foo:succeeded
__END__

TEST_NAME="${TEST_NAME_BASE}_datetime_offset"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}//2051/foo:succeeded" --offset=P1Y

contains_ok "${TEST_NAME}.stdout" <<__END__
2052/foo:succeeded
__END__

TEST_NAME="${TEST_NAME_BASE}_datetime_format"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}//20510101T0000Z/foo:succeeded" --offset=P1Y

contains_ok "${TEST_NAME}.stdout" <<__END__
2052/foo:succeeded
__END__

TEST_NAME="${TEST_NAME_BASE}_bad_point"
run_fail "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}//205/foo:succeeded"

contains_ok "${TEST_NAME}.stderr" <<__END__
InputError: Cycle point "205" is not compatible with DB point format "CCYY"
__END__

purge
