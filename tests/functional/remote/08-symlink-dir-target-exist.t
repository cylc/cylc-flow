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
# Test remote init fails if symlink dir target already exists

export REQUIRE_PLATFORM='loc:remote fs:indep comms:tcp'
. "$(dirname "$0")/test_header"
set_test_number 6

mapfile -d ' ' -t SSH_CMD < <(cylc config -d -i "[platforms][${CYLC_TEST_PLATFORM}]ssh command")
TEST_NAME="$(basename "$0")"

create_test_global_config "" "
[install]
    [[symlink dirs]]
        [[[${CYLC_TEST_INSTALL_TARGET}]]]
            run = \$HOME/cylctb-symlinks/$TEST_NAME/
"
install_workflow "${TEST_NAME_BASE}" basic

# shellcheck disable=SC2016
run_ok "${TEST_NAME_BASE}-mkdir" \
    "${SSH_CMD[@]}" "$CYLC_TEST_HOST" 'mkdir -p $HOME/cylc-symlink-test'

run_ok "${TEST_NAME_BASE}-val" cylc validate "$WORKFLOW_NAME"

# Run once to setup symlink dirs on remote install target
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach "$WORKFLOW_NAME"

# Remove remote run dir symlink (but not its target)
"${SSH_CMD[@]}" "$CYLC_TEST_HOST" "rm -rf ~/cylc-run/${WORKFLOW_NAME}"

# New run should abort
delete_db
TEST_NAME="${TEST_NAME_BASE}-run-again"
workflow_run_fail "$TEST_NAME" cylc play --no-detach "$WORKFLOW_NAME"

grep_ok "ERROR - platform: .* initialisation did not complete" "${TEST_NAME}.stderr"
grep_ok "WorkflowFilesError: Symlink dir target already exists" "${TEST_NAME}.stderr"

# Clean up remote symlink dir target
# shellcheck disable=SC2016
"${SSH_CMD[@]}" "$CYLC_TEST_HOST" 'rm -rf "${TMPDIR}/${USER}/sym-run" "${HOME}/cylctb-symlinks/$TEST_NAME/"'

purge
