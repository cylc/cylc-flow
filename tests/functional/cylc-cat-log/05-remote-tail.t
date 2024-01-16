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
# Test "cylc cat-log" with a custom remote tail command.
export REQUIRE_PLATFORM='loc:remote comms:tcp runner:background'
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
set -eu
SSH='ssh -oBatchMode=yes -oConnectTimeout=5'
SCP='scp -oBatchMode=yes -oConnectTimeout=5'
$SSH -n "${CYLC_TEST_HOST}" "mkdir -p cylc-run/.bin"
# shellcheck disable=SC2016
create_test_global_config "" "
[platforms]
   [[$CYLC_TEST_PLATFORM]]
        tail command template = \$HOME/cylc-run/.bin/my-tailer.sh %(filename)s"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
$SCP "${PWD}/bin/my-tailer.sh" \
    "${CYLC_TEST_HOST}:cylc-run/.bin/my-tailer.sh
"
#-------------------------------------------------------------------------------
# Run detached.
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
poll_grep_workflow_log -E '1/foo/01:preparing.* => submitted'
# cylc cat-log -m 't' tail-follows a file, so needs to be killed.
# Send interrupt signal to tail command after 15 seconds.
TEST_NAME="${TEST_NAME_BASE}-cat-log"
timeout -s 'INT' 15 \
    cylc cat-log "${WORKFLOW_NAME}//1/foo" -f 'o' -m 't' --force-remote \
    >"${TEST_NAME}.out" 2>"${TEST_NAME}.err" || true
grep_ok "HELLO from foo 1" "${TEST_NAME}.out"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-stop
run_ok "${TEST_NAME}" cylc stop --kill --max-polls=20 --interval=1 "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
$SSH -n "${CYLC_TEST_HOST}" "rm -rf cylc-run/.bin/"
purge
exit
