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
# Test all kinds of workflow-state DB checking.
. "$(dirname "$0")/test_header"

set_test_number 2

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Create Cylc 7, 8 (pre-8.3.0), and 8(8.3.0+) DBs for workflow-state checking.
DBDIR="${WORKFLOW_RUN_DIR}/dbs"
for x in c7 c8a c8b; do
  mkdir -p "${DBDIR}/${x}/log"
  sqlite3 "${DBDIR}/${x}/log/db" < "${x}.schema"
done

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${WORKFLOW_NAME}" --set="ALT=\"${DBDIR}\"" 
     
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" \
    cylc play "${WORKFLOW_NAME}" --set="ALT=\"${DBDIR}\"" \
        --reference-test --debug --no-detach

purge
