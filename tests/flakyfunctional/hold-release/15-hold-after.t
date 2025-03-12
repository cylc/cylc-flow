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
# Test cylc hold --after CYCLE_POINT.
# Test cylc play --hold-after CYCLE_POINT.

. "$(dirname "$0")/test_header"
set_test_number 4
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
# cylc hold --after=...
workflow_run_ok "${TEST_NAME_BASE}-1" \
    cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}"
sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    "SELECT cycle, name, status FROM task_pool WHERE cycle=='20140102T0000Z' ORDER BY name" \
    >'taskpool.out'
cmp_ok 'taskpool.out' <<'__OUT__'
20140102T0000Z|foo|waiting
__OUT__

delete_db
# cylc play --hold-after=...
workflow_run_ok "${TEST_NAME_BASE}-2" \
    cylc play --hold-after='20140101T1200Z' --reference-test --debug \
    --no-detach "${WORKFLOW_NAME}"

purge
exit
