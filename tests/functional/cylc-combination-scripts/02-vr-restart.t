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
# In this case the target workflow is stopped so cylc play is run.


. "$(dirname "$0")/test_header"
set_test_number 7

# Setup
WORKFLOW_NAME="cylctb-x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)"
cp "${TEST_SOURCE_DIR}/vr_workflow/flow.cylc" .
run_ok "setup (install)" \
    cylc install \
    --workflow-name "${WORKFLOW_NAME}"

export WORKFLOW_RUN_DIR="${RUN_DIR}/${WORKFLOW_NAME}"

# It validates and restarts:

# Change source workflow and run vr:
sed -i 's@P1Y@P5Y@' flow.cylc
run_ok "${TEST_NAME_BASE}-runs" cylc vr "${WORKFLOW_NAME}"

# Grep for vr reporting revalidation, reinstallation and playing the workflow.
grep "\$" "${TEST_NAME_BASE}-runs.stdout" > VIPOUT.txt
named_grep_ok "${TEST_NAME_BASE}-it-revalidated" "$ cylc validate --against-source" "VIPOUT.txt"
named_grep_ok "${TEST_NAME_BASE}-it-installed" "$ cylc reinstall" "VIPOUT.txt"
named_grep_ok "${TEST_NAME_BASE}-it-played" "cylc play" "VIPOUT.txt"
# Ensure that we don't have two copies of the workflow name
# https://github.com/cylc/cylc-flow/pull/5377
grep_fail "${WORKFLOW_NAME} ${WORKFLOW_NAME}" VIPOUT.txt


# Clean Up.
run_ok "teardown (stop workflow)" cylc stop "${WORKFLOW_NAME}" --now --now
purge
exit 0
