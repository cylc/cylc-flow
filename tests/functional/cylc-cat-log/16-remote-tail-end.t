#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) Earth Sciences New Zealand & British Crown (Met Office)
# & Contributors.
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
# Test "cylc cat-log" tail view modes with a custom remote tail command that
# honours the %(lines)s substitution:
#   * tail-from-start (-m t)   -> cylc sends "+1"  -> whole file
#   * tail-end       (-m te)   -> cylc sends "N"   -> last N lines only
# Also checks that a non-positive --tail-lines value is rejected.
export REQUIRE_PLATFORM='loc:remote fs:indep comms:tcp runner:background'
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 9
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
set -eu
SSH='ssh -oBatchMode=yes -oConnectTimeout=5'
SCP='scp -oBatchMode=yes -oConnectTimeout=5'
$SSH -n "${CYLC_TEST_HOST}" "mkdir -p cylc-run/.bin"
# shellcheck disable=SC2016
create_test_global_config "" "
[platforms]
   [[$CYLC_TEST_PLATFORM]]
        tail command template = \$HOME/cylc-run/.bin/my-tailer.sh %(lines)s %(filename)s
        retrieve job logs = False
"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
$SCP "${PWD}/bin/my-tailer.sh" \
    "${CYLC_TEST_HOST}:cylc-run/.bin/my-tailer.sh"
#-------------------------------------------------------------------------------
# Run detached.
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
poll_grep_workflow_log -E '1/foo/01:preparing.* => submitted'
# Wait until enough output exists on the job host that "tail-end" with a small
# line count cannot possibly include the first line (makes the test
# deterministic regardless of how fast the job host is writing output).
# shellcheck disable=SC2086
poll $SSH -n "${CYLC_TEST_HOST}" \
    "grep -qs -- 'from foo 10' 'cylc-run/${WORKFLOW_NAME}/log/job/1/foo/NN/job.out'"
#-------------------------------------------------------------------------------
# cylc cat-log tail modes follow the file, so each invocation needs to be
# killed; the custom tailer exits by itself but we add a timeout for safety.
#
# Scenario 1: tail-from-start (-m t) shows the whole file (cylc sends "+1"),
# so the very first line of output is present.
TEST_NAME="${TEST_NAME_BASE}-tail-from-start"
timeout -s 'INT' 15 \
    cylc cat-log "${WORKFLOW_NAME}//1/foo" -f 'o' -m 't' --force-remote \
    >"${TEST_NAME}.out" 2>"${TEST_NAME}.err" || true
grep_ok "HELLO from foo 1$" "${TEST_NAME}.out"
#-------------------------------------------------------------------------------
# Scenario 2: tail-end (-m te) with --tail-lines 3 shows only the last 3 lines
# (cylc sends "3"): exactly 3 lines of output, and NOT the first line.
TEST_NAME="${TEST_NAME_BASE}-tail-end-3"
timeout -s 'INT' 15 \
    cylc cat-log "${WORKFLOW_NAME}//1/foo" -f 'o' -m 'te' --tail-lines 3 \
    --force-remote >"${TEST_NAME}.out" 2>"${TEST_NAME}.err" || true
count_ok "HELLO from foo" "${TEST_NAME}.out" 3
grep_fail "HELLO from foo 1$" "${TEST_NAME}.out"
#-------------------------------------------------------------------------------
# Scenario 3: tail-end (-m te) with --tail-lines 1 shows just the last line.
TEST_NAME="${TEST_NAME_BASE}-tail-end-1"
timeout -s 'INT' 15 \
    cylc cat-log "${WORKFLOW_NAME}//1/foo" -f 'o' -m 'te' --tail-lines 1 \
    --force-remote >"${TEST_NAME}.out" 2>"${TEST_NAME}.err" || true
count_ok "HELLO from foo" "${TEST_NAME}.out" 1
#-------------------------------------------------------------------------------
# Scenario 4: a non-positive --tail-lines value is rejected (on the workflow
# host, before any remote invocation).
TEST_NAME="${TEST_NAME_BASE}-tail-lines-zero"
run_fail "${TEST_NAME}" \
    cylc cat-log "${WORKFLOW_NAME}//1/foo" -f 'o' -m 'te' --tail-lines 0 \
    --force-remote
grep_ok "--tail-lines must be a positive" "${TEST_NAME}.stderr"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-stop
run_ok "${TEST_NAME}" cylc stop --kill --max-polls=20 --interval=1 "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
$SSH -n "${CYLC_TEST_HOST}" "rm -rf cylc-run/.bin/"
purge
exit
