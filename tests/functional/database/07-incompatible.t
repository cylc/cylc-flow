#!/bin/bash
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
# Test that operating on a Cylc 7 workflow fails due to database incompatibility,
# and that suitable error message is given.

. "$(dirname "$0")/test_header"
set_test_number 6

install_workflow
# install the cylc7 restart database
SRV_DIR="${WORKFLOW_RUN_DIR}/.service"
mkdir "$SRV_DIR"
sqlite3 "${SRV_DIR}/db" < 'db.sqlite3'
sqlite3 "${SRV_DIR}/db" '.tables' > orig_tables.txt

run_ok "${TEST_NAME_BASE}-validate" cylc validate "$WORKFLOW_NAME"

TEST_NAME="${TEST_NAME_BASE}-play-fail"
run_fail "$TEST_NAME" cylc play "$WORKFLOW_NAME"
grep_ok \
    'Workflow database is incompatible with Cylc .*, or is corrupted' \
    "${TEST_NAME}.stderr"

# Check no new tables have been created
cmp_ok orig_tables.txt <<< "$(sqlite3 "${SRV_DIR}/db" '.tables')"

TEST_NAME="${TEST_NAME_BASE}-clean-fail"
run_fail "$TEST_NAME" cylc clean "$WORKFLOW_NAME"
grep_ok \
    'This database is either corrupted or not compatible with this' \
    "${TEST_NAME}.stderr"

purge

# Note: The test for "trying to restart a workflow without a database gives.
# suitable error message" was removed with the change from cylc run/restart to
# cylc play, as if the database is not present it will simply do a cold start.

exit
