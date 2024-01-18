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

# "cylc set" proposal examples: 1 - Carry on as if a failed task had succeeded
# https://cylc.github.io/cylc-admin/proposal-cylc-set.html#1-carry-on-as-if-a-failed-task-had-succeeded

. "$(dirname "$0")/test_header"
set_test_number 6

install_and_validate
reftest_run

for TASK in foo bar
do
    sqlite3 ~/cylc-run/"${WORKFLOW_NAME}"/log/db \
       "SELECT status FROM task_states WHERE name is \"$TASK\"" > "${TASK}.1"

    cmp_ok ${TASK}.1 - << __OUT__
succeeded
__OUT__

    sqlite3 ~/cylc-run/"${WORKFLOW_NAME}"/log/db \
       "SELECT outputs FROM task_outputs WHERE name is \"$TASK\"" > "${TASK}.2"

    # Json string list of outputs from the db may not be ordered correctly.
    # E.g., '["submitted", "started", "succeeded", "failed"]'.
    python3 - << __END__ > "${TASK}.3"
import json
with open("${TASK}.2", 'r') as f:
    print(
        ','.join(
            sorted(
                json.load(f)
             )
        )
    )
__END__

    cmp_ok "${TASK}.3" - << __OUT__
failed,started,submitted,succeeded
__OUT__

done
purge
