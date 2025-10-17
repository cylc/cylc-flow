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
# Ensure that validate step of `cylc vr` does not set the --icp option for the
# restart step, as this would cause an InputError.
# See https://github.com/cylc/cylc-flow/issues/6262

. "$(dirname "$0")/test_header"
set_test_number 2

WORKFLOW_ID=$(workflow_id)

cp -r "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/flow.cylc" .

run_ok "${TEST_NAME_BASE}-vip" cylc vip . \
    --workflow-name "${WORKFLOW_ID}" \
    --no-detach \
    --no-run-name \
    --mode simulation

echo "# Some Comment" >> flow.cylc

run_ok "${TEST_NAME_BASE}-vr" \
    cylc vr "${WORKFLOW_ID}" --no-detach --mode simulation
