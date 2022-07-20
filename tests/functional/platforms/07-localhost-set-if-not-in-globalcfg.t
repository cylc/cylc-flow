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
# Check that ``[platforms][localhost]`` is only set automatically if it
# not set in ``global.cylc``.

export REQUIRE_PLATFORM='runner:at'
. "$(dirname "$0")/test_header"

set_test_number 3

create_test_global_config "" "
    [platforms]
        [[localhost, nine_and_three_quarters]]
            hosts = localhost
            job runner = at
"

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

# Run the workflow
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

grep_ok "Job runner: at" "${WORKFLOW_RUN_DIR}/log/job/1/foo/NN/job"

purge
exit
