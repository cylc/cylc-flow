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
# Test `cylc vip` (Validate Install Play)

. "$(dirname "$0")/test_header"

set_test_number 4

WORKFLOW_NAME="cylctb-x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)"

cat > flow.cylc <<__HERE__
#!jinja2
# TEST: {{ CYLC_WORKFLOW_SRC_DIR }}
[scheduler]
    allow implicit tasks = true
[scheduling]
    [[graph]]
        R1 = foo
__HERE__

# It starts playing:
run_ok "${TEST_NAME_BASE}-vip" \
    cylc install \
        --no-run-name \
        --workflow-name "${WORKFLOW_NAME}"

# It can get CYLC_WORKFLOW_SRC_DIR
named_grep_ok "src-path-available" \
    "$PWD" "${RUN_DIR}/${WORKFLOW_NAME}/log/config/flow-processed.cylc"

# It can be updated with Cylc VR
echo "[meta]" >> flow.cylc
run_ok "${TEST_NAME_BASE}-vr" \
    cylc vr "${WORKFLOW_NAME}"
poll_grep "meta" "${RUN_DIR}/${WORKFLOW_NAME}/log/config/flow-processed.cylc"

# It can get CYLC_WORKFLOW_SRC_DIR
named_grep_ok "src-path-available" \
    "$PWD" "${RUN_DIR}/${WORKFLOW_NAME}/log/config/flow-processed.cylc"

purge "${WORKFLOW_NAME}"
