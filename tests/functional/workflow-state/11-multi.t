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

# shellcheck disable=SC2086

. "$(dirname "$0")/test_header"

set_test_number 35

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Create Cylc 7, 8 (pre-8.3.0), and 8(8.3.0+) DBs for workflow-state checking.
DBDIR="${WORKFLOW_RUN_DIR}/dbs"
for x in c7 c8a c8b; do
    mkdir -p "${DBDIR}/${x}/log"
    sqlite3 "${DBDIR}/${x}/log/db" < "${x}.sql"
done

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${WORKFLOW_NAME}" --set="ALT=\"${DBDIR}\""

grep_ok \
    "WARNING - (8.3.0) Deprecated function signature used for workflow_state xtrigger was automatically upgraded" \
    "${TEST_NAME_BASE}-validate.stderr"

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" \
    cylc play "${WORKFLOW_NAME}" --set="ALT=\"${DBDIR}\"" \
        --reference-test --debug --no-detach

# Single poll.
CMD="cylc workflow-state --run-dir=$DBDIR --max-polls=1"

# Content of the c8b DB:
# "select * from task_outputs"
#   1|foo|[1]|{"submitted": "submitted", "started": "started", "succeeded": "succeeded", "x": "the quick brown"}
# "select * from task_states"
#   foo|1|[1]|2024-06-05T16:34:02+12:00|2024-06-05T16:34:04+12:00|1|succeeded|0|0

#---------------
# Test the new-format command line (pre-8.3.0).
T=${TEST_NAME_BASE}-cli-c8b
run_ok "${T}-1" $CMD c8b
run_ok "${T}-2" $CMD c8b//1
run_ok "${T}-3" $CMD c8b//1/foo
run_ok "${T}-4" $CMD c8b//1/foo:succeeded
run_ok "${T}-5" $CMD "c8b//1/foo:the quick brown" --messages
run_ok "${T}-6" $CMD "c8b//1/foo:x" --triggers
run_ok "${T}-7" $CMD "c8b//1/foo:x"  # default to trigger if not a status
run_ok "${T}-8" $CMD c8b//1
run_ok "${T}-9" $CMD c8b//1:succeeded

run_fail "${T}-3" $CMD c8b//1/foo:failed
run_fail "${T}-5" $CMD "c8b//1/foo:the quick brown" --triggers
run_fail "${T}-5" $CMD "c8b//1/foo:x" --messages
run_fail "${T}-1" $CMD c8b//1:failed
run_fail "${T}-1" $CMD c8b//2
run_fail "${T}-1" $CMD c8b//2:failed

#---------------
T=${TEST_NAME_BASE}-cli-c8a
run_ok   "${T}-1" $CMD "c8a//1/foo:the quick brown" --messages
run_ok   "${T}-2" $CMD "c8a//1/foo:the quick brown" --triggers  # OK for 8.0 <= 8.3
run_fail "${T}-3" $CMD "c8a//1/foo:x" --triggers  # not possible for 8.0 <= 8.3

#---------------
T=${TEST_NAME_BASE}-cli-c7
run_ok   "${T}-1" $CMD "c7//1/foo:the quick brown" --messages
run_fail "${T}-2" $CMD "c7//1/foo:the quick brown" --triggers
run_ok   "${T}-3" $CMD "c7//1/foo:x" --triggers

#---------------
# Test the old-format command line (8.3.0+).
T=${TEST_NAME_BASE}-cli-8b-compat
run_ok "${T}-1" $CMD c8b
run_ok "${T}-2" $CMD c8b --point=1
run_ok "${T}-3" $CMD c8b --point=1 --task=foo
run_ok "${T}-4" $CMD c8b --point=1 --task=foo --status=succeeded
run_ok "${T}-5" $CMD c8b --point=1 --task=foo --message="the quick brown"
run_ok "${T}-6" $CMD c8b --point=1 --task=foo --output="the quick brown"

run_fail "${T}-7" $CMD c8b --point=1 --task=foo --status=failed
run_fail "${T}-8" $CMD c8b --point=1 --task=foo --message="x"
run_fail "${T}-9" $CMD c8b --point=1 --task=foo --output="x"
run_fail "${T}-10" $CMD c8b --point=2
run_fail "${T}-11" $CMD c8b --point=2 --task=foo --status="succeeded"

purge
