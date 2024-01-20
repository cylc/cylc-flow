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

# "cylc set" proposal examples: 4 -check that we can set a dead orphaned job to failed.
# https://cylc.github.io/cylc-admin/proposal-cylc-set.html#4-set-jobs-to-failed-when-a-job-platform-is-known-to-be-down

. "$(dirname "$0")/test_header"
set_test_number 4

install_and_validate

run_ok play-it cylc play --debug "${WORKFLOW_NAME}"

poll_grep_workflow_log -E "1/foo.* \(internal\)submitted"

cylc set -o failed "${WORKFLOW_NAME}//1/foo"

poll_grep_workflow_log -E "1/foo.* => failed"
poll_grep_workflow_log -E "1/foo.* did not complete required outputs"

cylc stop --now --now --interval=2 --max-polls=5 "${WORKFLOW_NAME}"

# Check the log for:
# - set completion message
# - implied outputs reported as already completed

grep_workflow_log_ok "${TEST_NAME_BASE}-grep-3" 'set: output 1/foo:failed completed'

# Check the DB records all the outputs.
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
failed,started,submitted
__OUT__

purge
