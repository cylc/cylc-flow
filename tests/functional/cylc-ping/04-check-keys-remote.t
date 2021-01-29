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
export REQUIRE_PLATFORM='loc:remote comms:tcp'
. "$(dirname "$0")/test_header"
set_test_number 5

init_suite "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
#!jinja2
[scheduler]
[scheduling]
    [[graph]]
        R1 = holder => held
[runtime]
    [[holder]]
        script = cylc hold "${CYLC_SUITE_NAME}"
        platform = {{CYLC_TEST_PLATFORM}}
    [[held]]
        script = true
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}" \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}" \
    --debug -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'"
RRUND="cylc-run/${SUITE_NAME}"
RSRVD="${RRUND}/.service"
poll_grep_suite_log 'Holding all waiting or queued tasks now'
SSH='ssh -n -oBatchMode=yes -oConnectTimeout=5'
 
${SSH} "${CYLC_TEST_HOST}" \
find "${RSRVD}" -type f -name "*key*"|awk -F/ '{print $NF}'|sort >'find.out'

sort >'keys'<<__OUT__
client_${CYLC_TEST_INSTALL_TARGET}.key
client.key_secret
server.key
__OUT__
cmp_ok 'find.out' 'keys'
cylc stop --max-polls=60 --interval=1 "${SUITE_NAME}"

grep_ok "Removing authentication keys and contact file from remote: \"${CYLC_TEST_INSTALL_TARGET}\"" "${SUITE_RUN_DIR}/log/suite/log"
${SSH} "${CYLC_TEST_HOST}" \
find "${RRUND}" -type f -name "*key*"|awk -F/ '{print $NF}'|sort >'find.out'
cmp_ok 'find.out' <<'__OUT__'
__OUT__
purge
exit
