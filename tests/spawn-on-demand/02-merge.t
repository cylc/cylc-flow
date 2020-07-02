#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

# Check that reflows merge correctly if they catch up.
. "$(dirname "$0")/test_header"
install_suite "${TEST_NAME_BASE}"

set_test_number 5

# validate
TEST_NAME="${TEST_NAME_BASE}"-validate
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

# reference test
TEST_NAME="${TEST_NAME_BASE}"-run
suite_run_ok "${TEST_NAME}" cylc run --reference-test --no-detach "${SUITE_NAME}"

# extract flow labels from job files
eval $(cylc cat-log -s 1 -f j "${SUITE_NAME}" foo.1 | grep CYLC_TASK_FLOW_LABEL)
FLOW_ONE="${CYLC_TASK_FLOW_LABEL}"

eval $(cylc cat-log -s 2 -f j "${SUITE_NAME}" foo.1 | grep CYLC_TASK_FLOW_LABEL)
FLOW_TWO="${CYLC_TASK_FLOW_LABEL}"

eval $(cylc cat-log -s 1 -f j "${SUITE_NAME}" bar.3 | grep CYLC_TASK_FLOW_LABEL)
FLOW_MERGED="${CYLC_TASK_FLOW_LABEL}"

# compare with expected tasks in each flow (original, reflow, merged)
sqlite3 ~/cylc-run/"${SUITE_NAME}"/log/db \
   "SELECT name, cycle, submit_num FROM task_states \
       WHERE flow_label is \"${FLOW_ONE}\" order by cycle" \
          > flow-one.db

cmp_ok flow-one.db - << __OUT__
foo|1|1
bar|1|1
foo|2|1
bar|2|1
foo|3|1
__OUT__

sqlite3 ~/cylc-run/"${SUITE_NAME}"/log/db \
   "SELECT name, cycle, submit_num FROM task_states \
       WHERE flow_label is \"${FLOW_TWO}\" order by cycle" \
          > flow-two.db

cmp_ok flow-two.db - << __OUT__
foo|1|2
bar|1|2
foo|2|2
bar|2|2
__OUT__

sqlite3 ~/cylc-run/"${SUITE_NAME}"/log/db \
   "SELECT name, cycle, submit_num FROM task_states \
       WHERE flow_label is \"${FLOW_MERGED}\" order by cycle" \
          > flow-merged.db

# foo.3 appears here too because a new task_states row is written for the merged label
cmp_ok flow-merged.db - << __OUT__
foo|3|1
bar|3|1
__OUT__

purge_suite "${SUITE_NAME}"
exit
