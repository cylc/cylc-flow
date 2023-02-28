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
# Test `cylc vr` (Validate Reinstall restart)
# Test that args for re-invocation are correct:
export REQUIRE_PLATFORM='loc:remote runner:background fs:shared'
. "$(dirname "$0")/test_header"

set_test_number 4

create_test_global_config '' """
[scheduler]
    [[run hosts]]
        available = ${CYLC_TEST_HOST}

"""

# Setup
WORKFLOW_NAME="cylctb-x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)"
cp "${TEST_SOURCE_DIR}/vr_workflow/flow.cylc" .
sed -i 's@pause@stop --now --now@' flow.cylc
run_ok "setup (install)" \
    cylc vip \
    --workflow-name "${WORKFLOW_NAME}" \
    --no-detach

# It validates and restarts:
# Change source workflow and run vr:
sed -i 's@P1Y@P5Y@' flow.cylc
TEST_NAME="${TEST_NAME_BASE}-reinvoke"
run_ok "${TEST_NAME}" cylc vr "${WORKFLOW_NAME}"

grep_fail \
    "${WORKFLOW_NAME} ${WORKFLOW_NAME}/run1" \
    "${TEST_NAME}.stderr"

# Clean Up.
run_ok "teardown (stop workflow)" cylc stop "${WORKFLOW_NAME}" --now --now
purge
exit 0
