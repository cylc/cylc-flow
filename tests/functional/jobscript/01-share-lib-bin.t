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
# CYLC_WORKFLOW_SHARE_DIR/bin is added to the PATH
# CYLC_WORKFLOW_SHARE_DIR/lib/python is added to PYTHONPATH
#
# Workflow creates scripts in CYLC_WORKFLOW_SHARE_DIR in `install_cold` task
# Which are then used in subsequent tasks. We check for the output of those
# tasks.
. "$(dirname "$0")/test_header"
set_test_number 2

# Setup:
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}.validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}.play" cylc play --no-detach "${WORKFLOW_NAME}"

purge
