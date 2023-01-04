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
# Test `cylc vro` (Validate Reinstall reload)
# In this case the target workflow is running so cylc reload is run.

. "$(dirname "$0")/test_header"
set_test_number 6


# Setup (Must be a running workflow, note the unusual absence of --no-detach)
WORKFLOW_NAME="cylctb-x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)"
cp "${TEST_SOURCE_DIR}/vro_workflow/flow.cylc" .
run_ok "setup (vip)" \
    cylc vip --debug \
    --workflow-name "${WORKFLOW_NAME}" \
    --no-run-name
export WORKFLOW_RUN_DIR="${RUN_DIR}/${WORKFLOW_NAME}"
poll_workflow_running


# It validates and reloads:

sed -i 's@P1Y@P5Y@' flow.cylc
run_ok "${TEST_NAME_BASE}-runs" cylc vro "${WORKFLOW_NAME}"

# Grep for VRO reporting revalidation, reinstallation and reloading
grep "\$" "${TEST_NAME_BASE}-runs.stdout" > VIPOUT.txt
named_grep_ok "${TEST_NAME_BASE}-it-revalidated" "$ cylc validate --against-source" "VIPOUT.txt"
named_grep_ok "${TEST_NAME_BASE}-it-installed" "$ cylc reinstall" "VIPOUT.txt"
named_grep_ok "${TEST_NAME_BASE}-it-reloaded" "$ cylc reload" "VIPOUT.txt"


# Clean Up.
run_ok "teardown (stop workflow)" cylc stop "${WORKFLOW_NAME}" --now --now
purge
exit 0
