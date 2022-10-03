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
# -----------------------------------------------------------------------------
# Test that cylc clean succesfully removes the workflow on remote host even
# when there is a leftover contact file with an unreachable host recorded in it

export REQUIRE_PLATFORM='loc:remote fs:indep comms:tcp'
. "$(dirname "$0")/test_header"
set_test_number 3

SSH_CMD="$(cylc config -d -i "[platforms][${CYLC_TEST_PLATFORM}]ssh command") ${CYLC_TEST_HOST}"

init_workflow "${TEST_NAME_BASE}" << __FLOW__
[scheduling]
    [[graph]]
        R1 = dilophosaurus
[runtime]
    [[dilophosaurus]]
        platform = ${CYLC_TEST_PLATFORM}
__FLOW__


run_ok "${TEST_NAME_BASE}-validate" cylc validate "$WORKFLOW_NAME"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "$WORKFLOW_NAME" --no-detach

# Create a fake old contact file on the remote host
echo | $SSH_CMD "cat > \$HOME/cylc-run/${WORKFLOW_NAME}/.service/contact" << EOF
CYLC_API=5
CYLC_VERSION=8.1.0
CYLC_WORKFLOW_COMMAND=echo Hello John
CYLC_WORKFLOW_HOST=unreachable.isla_nublar.ingen
CYLC_WORKFLOW_ID=${WORKFLOW_NAME}
CYLC_WORKFLOW_PID=99999
CYLC_WORKFLOW_PORT=00000
EOF

TEST_NAME="cylc-clean"
run_ok "$TEST_NAME" cylc clean --remote "$WORKFLOW_NAME"
dump_std "$TEST_NAME"

purge
