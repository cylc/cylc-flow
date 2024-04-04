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
export REQUIRE_PLATFORM='loc:remote fs:shared runner:background'
. "$(dirname "$0")/test_header"
set_test_number 3
#-------------------------------------------------------------------------------

# The Cylc CLI can "infer" run numbers e.g. `cylc play foo` might run `foo/run1`.
# This makes monitoring difficult because you can't see what workflow run a Cylc
# process is running so when/if we re-invoke the `cylc play` command on a remote
# host we use the full ID (including the run number) not the abbreviated version.

# install a workflow *with* the standard run numbers
echo '
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[graph]]
        R1 = one
' > flow.cylc
init_workflow "${TEST_NAME_BASE}" flow.cylc true
WORKFLOW_RUN_DIR="$WORKFLOW_RUN_DIR/run1"  # allow poll_workflow to work

# get the workflow to startup on the test platform
create_test_global_config '' "
[scheduler]
    [[run hosts]]
        available = ${CYLC_TEST_HOST}
"

# run the workflow
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --pause "${WORKFLOW_NAME}"
poll_workflow_running

# extract the command being run from the contact file
run_ok "${TEST_NAME_BASE}-cmd" \
    cylc get-workflow-contact "${WORKFLOW_NAME}"
sed -n -i 's/CYLC_WORKFLOW_COMMAND=.*cylc //p' "${TEST_NAME_BASE}-cmd.stdout"

# ensure the whole workflow ID is present in the command (including the run number)
CMD="^play --pause ${WORKFLOW_NAME}/run1 --host=localhost --color=never$"
if grep "${CMD}" "${TEST_NAME_BASE}-cmd.stdout"; then
    ok "${TEST_NAME_BASE}-re-invoked-id"
else
    fail "${TEST_NAME_BASE}-re-invoked-id"
fi

# shutdown
cylc stop "${WORKFLOW_NAME}"
poll_workflow_stopped

purge
exit
