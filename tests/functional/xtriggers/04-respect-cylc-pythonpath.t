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
#------------------------------------------------------------------------------

# An xtrigger added to $CYLC_PYTHONPATH should take precedence
# over a `cylc.xtriggers` entry point of the same name

. "$(dirname "$0")/test_header"
set_test_number 3

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Install the succeeding xtrigger function.
export CYLC_PYTHONPATH=${WORKFLOW_RUN_DIR}/dir:${CYLC_PYTHONPATH:-}

# Validate the test workflow.
run_ok "${TEST_NAME_BASE}-val" cylc validate --debug "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play --no-detach --debug "${WORKFLOW_NAME}"

# Check the result of xtrigger.
grep_workflow_log_ok "${TEST_NAME_BASE}-grep" "echo overridden, args=('the_args',)"

purge
