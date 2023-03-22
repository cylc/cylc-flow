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

set_test_number 3

create_test_global_config '' """
[scheduler]
    [[run hosts]]
        available = ${CYLC_TEST_HOST}

"""

# Setup
WORKFLOW_NAME="cylctb-x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)"
cp "${TEST_SOURCE_DIR}/vr_workflow_stop/flow.cylc" .
run_ok "${TEST_NAME_BASE}-install" \
    cylc vip \
    --workflow-name "${WORKFLOW_NAME}" \
    --no-detach

# It validates and restarts:
# Change source workflow and run vr:
TEST_NAME="${TEST_NAME_BASE}-reinvoke"
run_ok "${TEST_NAME}" cylc vr "${WORKFLOW_NAME}" --no-detach

ls "${RUN_DIR}/${WORKFLOW_NAME}/runN/log/scheduler" > logdir.txt
cmp_ok logdir.txt <<__HERE__
01-start-01.log
02-start-01.log
log
__HERE__

# Clean Up.
purge
exit 0
