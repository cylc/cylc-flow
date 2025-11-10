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
# Test "cylc cat-log" exits when the log file is deleted
# or when tail is killed.

. "$(dirname "$0")/test_header"
set_test_number 2

# Get PID of tail cmd given the parent cat-log PPID
get_tail_pid() {
    pgrep -P "$1" tail
}

init_workflow "${TEST_NAME_BASE}" << __EOF__
# whatever
__EOF__

log_file="${WORKFLOW_RUN_DIR}/log/foo.log"
echo "Hello, Mr. Thompson" > "$log_file"

export CYLC_PROC_POLL_INTERVAL=0.5

TEST_NAME="${TEST_NAME_BASE}-delete"
cylc cat-log --mode=tail "$WORKFLOW_NAME" -f foo.log 2>&1 &
cat_log_pid="$!"
# Wait for tail to start
poll get_tail_pid "$cat_log_pid"
# We should be able to delete the log file
run_ok "$TEST_NAME" rm "$log_file"
# cat-log should exit (but exit code does not seem to be consistent across systems)
poll_pid_done "$cat_log_pid"

echo "Hello, Mr. Thompson" > "$log_file"

TEST_NAME="${TEST_NAME_BASE}-kill"
cylc cat-log --mode=tail "$WORKFLOW_NAME" -f foo.log 2>&1 &
cat_log_pid="$!"
# Wait for tail to start
poll get_tail_pid "$cat_log_pid"
kill "$(get_tail_pid "$cat_log_pid")"
# cat-log should exit non-zero
poll_pid_done "$cat_log_pid"
run_fail "${TEST_NAME}_ret" wait "$cat_log_pid"

purge
