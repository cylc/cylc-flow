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

# Test the development main-loop plugins to ensure they can run to completion

. "$(dirname "$0")/test_header"

expected_log_files=(
    # these are the files they should produce
    cylc.flow.main_loop.log_data_store.json
    cylc.flow.main_loop.log_data_store.pdf
    cylc.flow.main_loop.log_db.sql
    cylc.flow.main_loop.log_main_loop.json
    cylc.flow.main_loop.log_main_loop.pdf
    cylc.flow.main_loop.log_memory.json
    cylc.flow.main_loop.log_memory.pdf
)

set_test_number $(( 1 + ${#expected_log_files[@]} ))

init_workflow "${TEST_NAME_BASE}" <<__FLOW_CYLC__
[scheduler]
    # make sure periodic plugins actually run
    [[main loop]]
        [[[log data store]]]
            interval = PT1S
        [[[log main loop]]]
            interval = PT1S
        [[[log memory]]]
            interval = PT1S

[scheduling]
    [[graph]]
        R1 = a

[runtime]
    [[a]]
        script = sleep 5
__FLOW_CYLC__

# run a workflow with all the development main-loop plugins turned on
run_ok "${TEST_NAME_BASE}-run" \
    cylc play "${WORKFLOW_NAME}" \
        --no-detach \
        --debug \
        --main-loop 'log data store' \
        --main-loop 'log db' \
        --main-loop 'log main loop' \
        --main-loop 'log memory'

# check the expected files are generated
for log_file in "${expected_log_files[@]}"; do
    file_path="${HOME}/cylc-run/${WORKFLOW_NAME}/${log_file}"
    run_ok "${TEST_NAME_BASE}.${log_file}" \
        stat "${file_path}"
done

purge
