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
# Test restart with broadcast to "[events]submission timeout".
. "$(dirname "$0")/test_header"
set_test_number 4
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --debug --no-detach
sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
  'SELECT * FROM broadcast_states' >'sqlite3.out'
cmp_ok 'sqlite3.out' <<<'*|root|[events]submission timeout|PT1M'
workflow_run_ok "${TEST_NAME_BASE}-restart" \
    cylc play "${WORKFLOW_NAME}" --debug --no-detach --reference-test
purge
exit
