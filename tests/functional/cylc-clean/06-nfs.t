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
# -----------------------------------------------------------------------------
# This test covers the interaction between "cylc clean" and "cylc cat-log -m t"
# on the NFS filesystem. The "cat-log" should not block the "clean".
#
# Tests: https://github.com/cylc/cylc-flow/pull/5359
#
# If you try to delete a file that is stored on NFS, which is open for reading
# by another process (e.g. `tail -f`), NFS will remove the file, but put a
# ".nfs" file in its place. This ".nfs" file will cause "rm" operations on
# the directory containing the NFS files to fail with one of two errors:
# * https://docs.python.org/3/library/errno.html#errno.EBUSY
# * https://docs.python.org/3/library/errno.html#errno.ENOTEMPTY
#
# To prevent "cylc cat-log -m t" which calls "tail -f" from blocking
# "cylc clean" commands, we retry the "rm" operation with a delay. This
# allows the "tail -f" to fail and release its file lock allowing the
# "rm" to pass on a subsequent attempt.

. "$(dirname "$0")/test_header"
if [[ $OSTYPE == darwin* ]]; then
    skip_all "don't run test on Mac OS (BSD uses different error messages)"
fi
set_test_number 4

# install a blank source workflow
init_workflow "${TEST_NAME_BASE}" <<< '# blank workflow'

# add a scheduler log file with something written to it
WORKFLOW_LOG_DIR="${WORKFLOW_RUN_DIR}/log/scheduler"
mkdir -p "$WORKFLOW_LOG_DIR"
LOG_STUFF='foo bar baz'
echo "${LOG_STUFF}" > "${WORKFLOW_LOG_DIR}/log"

# start cat-log running - this runs "tail -f"
cylc cat-log -m t "$WORKFLOW_NAME" > out 2>err & PID="$!"

# wait for cat-log to reach the end of the file
for _retry in $(seq 1 5); do
    echo "# try $_retry"
    if [[ "$(cat out)" != "$LOG_STUFF" ]]; then
        sleep 1
    fi
done
cmp_ok out <<< "$LOG_STUFF"

# try to clean the workflow
run_ok "${TEST_NAME_BASE}-clean" cylc clean -y "${WORKFLOW_NAME}"

# the tail command should have detected that the file isn't there any more
# and released the file handle
grep_ok 'has become inaccessible' err

# ensure the log dir was removed correctly
# run_ok "${TEST_NAME_BASE}-dir-removed" [[ ! -d "${WORKFLOW_LOG_DIR}" ]]
TEST_NAME="${TEST_NAME_BASE}-log-dir-removed"
if [[ -d "${WORKFLOW_LOG_DIR}" ]]; then
    fail "${TEST_NAME}"
else
    ok "${TEST_NAME}"
fi

# kill the cat-log process group (will include the tail process)
pkill -P "${PID}" 2>/dev/null || true

purge
exit
