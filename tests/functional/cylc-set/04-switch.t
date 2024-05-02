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

# "cylc set" proposal examples: 5 - Set and complete a future switch task with the "--wait" flag
# https://cylc.github.io/cylc-admin/proposal-cylc-set.html#5-set-switch-tasks-at-an-optional-branch-point-to-direct-the-future-flow

. "$(dirname "$0")/test_header"
set_test_number 5

install_and_validate
reftest_run

# The branch-point task foo should be recorded as succeeded.

sqlite3 ~/cylc-run/"${WORKFLOW_NAME}"/log/db \
   "SELECT status FROM task_states WHERE name is \"foo\"" > db-foo.2

cmp_ok "db-foo.2" - << __OUT__
succeeded
__OUT__

# the outputs of foo should be recorded as:
#   a, succeeded
# and the implied outputs (of succeeded) as well:
#   submitted, started

sqlite3 ~/cylc-run/"${WORKFLOW_NAME}"/log/db \
   "SELECT outputs FROM task_outputs WHERE name is \"foo\"" > db-foo.1

# Json string list of outputs from the db may not be ordered correctly.
python3 - << __END__ > db-foo.2
import json
with open("db-foo.1", 'r') as f:
    print(
        ','.join(
            sorted(
                json.load(f)
             )
        )
    )
__END__

cmp_ok "db-foo.2" - << __OUT__
a,started,submitted,succeeded
__OUT__

# Check the flow-wait worked
grep_workflow_log_ok check-wait "1/foo.* spawning outputs after flow-wait" -E

purge
