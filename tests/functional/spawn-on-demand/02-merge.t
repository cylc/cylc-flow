#!/usr/bin/env bash
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

# Check that reflows merge correctly if they catch up, AND that redundant flow
# labels get merged.

. "$(dirname "$0")/test_header"
install_suite "${TEST_NAME_BASE}"

set_test_number 6

# validate
TEST_NAME="${TEST_NAME_BASE}"-validate
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

# Set frequent pruning of merged flow labels.
create_test_globalrc "" "
[cylc]
   [[main loop]]
       [[[prune flow labels]]]
            interval = PT10S"

# reference test
TEST_NAME="${TEST_NAME_BASE}"-run
suite_run_ok "${TEST_NAME}" cylc run --reference-test --no-detach "${SUITE_NAME}"

# extract flow labels from job files
# shellcheck disable=SC2046
eval $(cylc cat-log -s 1 -f j "${SUITE_NAME}" foo.1 | grep CYLC_TASK_FLOW_LABEL)
FLOW_ONE="${CYLC_TASK_FLOW_LABEL}"

# shellcheck disable=SC2046
eval $(cylc cat-log -s 2 -f j "${SUITE_NAME}" foo.1 | grep CYLC_TASK_FLOW_LABEL)
FLOW_TWO="${CYLC_TASK_FLOW_LABEL}"

# shellcheck disable=SC2046
eval $(cylc cat-log -s 1 -f j "${SUITE_NAME}" bar.3 | grep CYLC_TASK_FLOW_LABEL)
FLOW_MERGED="${CYLC_TASK_FLOW_LABEL}"

# shellcheck disable=SC2046
eval $(cylc cat-log -s 1 -f j "${SUITE_NAME}" baz.3 | grep CYLC_TASK_FLOW_LABEL)
FLOW_PRUNED="${CYLC_TASK_FLOW_LABEL}"

# compare with expected tasks in each flow (original, reflow, merged, pruned)
sqlite3 ~/cylc-run/"${SUITE_NAME}"/log/db \
   "SELECT name, cycle, flow_label FROM task_states \
       WHERE submit_num is 1 order by cycle" \
          > flow-one.db

run_ok check_merged_label eval "test $FLOW_MERGED == $FLOW_ONE$FLOW_TWO || \
                        test $FLOW_MERGED == $FLOW_TWO$FLOW_ONE"

run_ok check_pruned_label eval "test $FLOW_PRUNED == $FLOW_ONE || \
                        test $FLOW_PRUNED == $FLOW_TWO"

cmp_ok flow-one.db - << __OUT__
foo|1|${FLOW_ONE}
bar|1|${FLOW_ONE}
baz|1|${FLOW_ONE}
foo|2|${FLOW_ONE}
bar|2|${FLOW_ONE}
baz|2|${FLOW_ONE}
foo|3|${FLOW_ONE}
foo|3|${FLOW_MERGED}
bar|3|${FLOW_MERGED}
baz|3|${FLOW_PRUNED}
__OUT__

sqlite3 ~/cylc-run/"${SUITE_NAME}"/log/db \
   "SELECT name, cycle, flow_label FROM task_states \
       WHERE submit_num is 2 order by cycle" \
          > flow-two.db

cmp_ok flow-two.db - << __OUT__
foo|1|${FLOW_TWO}
bar|1|${FLOW_TWO}
baz|1|${FLOW_TWO}
foo|2|${FLOW_TWO}
bar|2|${FLOW_TWO}
baz|2|${FLOW_TWO}
__OUT__

purge_suite "${SUITE_NAME}"
exit
