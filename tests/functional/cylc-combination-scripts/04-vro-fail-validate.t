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
# Test `cylc vro` (Validate Reinstall restart)
# Changes to the source cause VRO to bail on validation.

. "$(dirname "$0")/test_header"
set_test_number 5

# Setup
WORKFLOW_NAME="cylctb-x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)"
cp "${TEST_SOURCE_DIR}/vro_workflow/flow.cylc" .
run_ok "setup (vip)" \
    cylc vip --debug \
    --workflow-name "${WORKFLOW_NAME}" \
    --no-run-name \


# Change source workflow and run vro:

# Cut the runtime section out of the source flow.
head -n 5 > tmp < flow.cylc
cat tmp > flow.cylc

TEST_NAME="${TEST_NAME_BASE}"
run_fail "${TEST_NAME}" cylc vro "${WORKFLOW_NAME}"

# Grep for reporting of revalidation, reinstallation, reloading and playing:
named_grep_ok "${TEST_NAME_BASE}-it-tried" \
    "$ cylc validate --against-source" "${TEST_NAME}.stdout"
named_grep_ok "${TEST_NAME_BASE}-it-failed" \
    "WorkflowConfigError" "${TEST_NAME}.stderr"


# Clean Up:
run_ok "teardown (stop workflow)" cylc stop "${WORKFLOW_NAME}" --now --now
purge
exit 0
