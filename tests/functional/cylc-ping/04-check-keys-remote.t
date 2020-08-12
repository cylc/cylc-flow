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
# Checks remote ZMQ keys are created and deleted on shutdown.
. "$(dirname "$0")/test_header"

require_remote_platform

set_test_number 4

init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
#!jinja2
[cylc]
[scheduling]
    [[graph]]
        R1 = holder => held
[runtime]
    [[holder]]
        script = """cylc hold "${CYLC_SUITE_NAME}" """
        platform = {{CYLC_REMOTE_PLATFORM}}
    [[held]]
        script = true
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}" \
    -s "CYLC_REMOTE_PLATFORM=${CYLC_REMOTE_PLATFORM}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}" \
    -s "CYLC_REMOTE_PLATFORM=${CYLC_REMOTE_PLATFORM}"
RRUND="cylc-run/${SUITE_NAME}"
RSRVD="${RRUND}/.service"
poll_grep_suite_log 'Holding all waiting or queued tasks now'
SSH='ssh -n -oBatchMode=yes -oConnectTimeout=5'
${SSH} "${CYLC_TEST_HOST}" \
find "${RSRVD}" -type f -name "*key*"|awk -F/ '{print $NF}'|sort >'find.out'
cmp_ok 'find.out' <<'__OUT__'
client.key
client.key_secret
server.key
__OUT__
cylc stop --max-polls=60 --interval=1 "${SUITE_NAME}"
${SSH} "${CYLC_TEST_HOST}" \
find "${RRUND}" -type f -name "*key*"|awk -F/ '{print $NF}'|sort >'find.out'
cmp_ok 'find.out' <<'__OUT__'
__OUT__
purge_suite_remote "${CYLC_TEST_HOST}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
