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
# Test "cylc cat-log" with a custom remote tail command.
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
require_remote_platform
#-------------------------------------------------------------------------------
set_test_number 4
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
set -eu
SSH='ssh -oBatchMode=yes -oConnectTimeout=5'
SCP='scp -oBatchMode=yes -oConnectTimeout=5'
$SSH -n "${CYLC_REMOTE_PLATFORM}" "mkdir -p cylc-run/.bin"
# shellcheck disable=SC2016
create_test_globalrc "" "
[job platforms]
   [[$CYLC_REMOTE_PLATFORM]]
        tail command template = \$HOME/cylc-run/.bin/my-tailer.sh %(filename)s"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
$SCP "${PWD}/bin/my-tailer.sh" \
    "${CYLC_REMOTE_PLATFORM}:cylc-run/.bin/my-tailer.sh
"
#-------------------------------------------------------------------------------
# Run detached.
suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"
#-------------------------------------------------------------------------------
poll_grep_suite_log -F '[foo.1] status=submitted: (received)started'
# cylc cat-log -m 't' tail-follows a file, so needs to be killed.
# Send interrupt signal to tail command after 15 seconds.
TEST_NAME="${TEST_NAME_BASE}-cat-log"
timeout -s 'INT' 15 \
    cylc cat-log "${SUITE_NAME}" -f 'o' -m 't' 'foo.1' --force-remote \
    >"${TEST_NAME}.out" 2>"${TEST_NAME}.err" || true
grep_ok "HELLO from foo 1" "${TEST_NAME}.out"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-stop
run_ok "${TEST_NAME}" cylc stop --kill --max-polls=20 --interval=1 "${SUITE_NAME}"
#-------------------------------------------------------------------------------
purge_suite_platform "${CYLC_REMOTE_PLATFORM}" "${SUITE_NAME}"
$SSH -n "${CYLC_REMOTE_PLATFORM}" "rm -rf cylc-run/.bin/"
purge_suite "${SUITE_NAME}"
exit
