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

# Check that flows merge correctly.

. "$(dirname "$0")/test_header"
install_workflow "${TEST_NAME_BASE}"

set_test_number 4

TEST_NAME="${TEST_NAME_BASE}"-validate
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}"-run
workflow_run_ok "${TEST_NAME}" cylc play --reference-test \
   --debug --no-detach "${WORKFLOW_NAME}"

# check the DB as well
sqlite3 ~/cylc-run/"${WORKFLOW_NAME}"/log/db \
   "SELECT name, cycle, flows FROM task_states \
       WHERE submit_num is 1 order by cycle" \
          > flow-one.db

cmp_ok flow-one.db - << __OUT__
foo|1|["original"]
bar|1|["original"]
foo|2|["original"]
bar|2|["original"]
foo|3|["original"]
foo|3|["original", "other"]
bar|3|["original", "other"]
__OUT__

sqlite3 ~/cylc-run/"${WORKFLOW_NAME}"/log/db \
   "SELECT name, cycle, flows FROM task_states \
       WHERE submit_num is 2 order by cycle" \
          > flow-two.db

cmp_ok flow-two.db - << __OUT__
foo|1|["other"]
bar|1|["other"]
foo|2|["other"]
bar|2|["other"]
__OUT__

purge
exit
