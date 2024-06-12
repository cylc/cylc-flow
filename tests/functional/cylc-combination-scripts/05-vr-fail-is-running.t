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
# Test `cylc vr` (Validate Reinstall)
# In this case the target workflow is in an abiguous state: We cannot tell
# Whether it's running, paused or stopped. Cylc VR should validate before
# reinstall:

. "$(dirname "$0")/test_header"
set_test_number 4

create_test_global_config "" """
[scheduler]
    [[main loop]]
        plugins = reset bad hosts
"""

# Setup
WORKFLOW_NAME="cylctb-x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)"
cp "${TEST_SOURCE_DIR}/vr_workflow/flow.cylc" .
run_ok "setup (vip)" \
    cylc vip --debug \
    --workflow-name "${WORKFLOW_NAME}" \
    --no-run-name


# Get the workflow into an unreachable state
CONTACTFILE="${RUN_DIR}/${WORKFLOW_NAME}/.service/contact"
cp "$CONTACTFILE" "${CONTACTFILE}.old"
poll test -e "${CONTACTFILE}"

sed -i 's@CYLC_WORKFLOW_HOST=.*@CYLC_WORKFLOW_HOST=elephantshrew@' "${CONTACTFILE}"


# It can't figure out whether the workflow is running:

# Change source workflow and run vr:
run_fail "${TEST_NAME_BASE}-runs" cylc vr "${WORKFLOW_NAME}"

grep_ok "on elephantshrew." "${TEST_NAME_BASE}-runs.stderr"

# Clean Up:
mv "${CONTACTFILE}.old" "$CONTACTFILE"
run_ok "${TEST_NAME_BASE}-stop" cylc stop "${WORKFLOW_NAME}" --now --now
purge
exit 0
