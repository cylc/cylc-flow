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
# Checks remote ZMQ keys are created and deleted on shutdown.
export REQUIRE_PLATFORM='loc:remote'
. "$(dirname "$0")/test_header"
set_test_number 5

create_test_global_config '' "
[platforms]
    [[$CYLC_TEST_PLATFORM]]
        retrieve job logs = True
"

init_workflow "${TEST_NAME_BASE}" <<__FLOW_CONFIG__
[scheduling]
    [[graph]]
        R1 = keys

[runtime]
    [[keys]]
        platform = $CYLC_TEST_PLATFORM
        script = """
            find \
                "\${CYLC_WORKFLOW_RUN_DIR}" \
                -type f \
                -name "*key*" \
                | awk -F/ '{print \$NF}'|sort > "\${CYLC_TASK_LOG_ROOT}-find-out"
        """
        [[[environment]]]
            LANG = C
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate \
    "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play \
    "${WORKFLOW_NAME}" \
    --no-detach

KEYS_FILE="$(cylc cat-log -m p "$WORKFLOW_NAME" 'keys.1' -f job-find-out)"
if [[ "$CYLC_TEST_PLATFORM" == *shared* ]]; then
    cmp_ok "$KEYS_FILE" <<__OUT__
client.key_secret
client_${CYLC_TEST_INSTALL_TARGET}.key
server.key
server.key_secret
__OUT__
else
    cmp_ok "$KEYS_FILE" <<__OUT__
client.key_secret
client_${CYLC_TEST_INSTALL_TARGET}.key
server.key
__OUT__
fi

if [[ "$CYLC_TEST_PLATFORM" == *shared* ]]; then
    skip 1
else
    # NOTE: remote tidy happens on a random platform picked from the install
    # target so might not be $CYLC_TEST_PLATFORM
    grep_ok \
        "platform: .* - remote tidy (on $CYLC_TEST_HOST)" \
        "${WORKFLOW_RUN_DIR}/log/workflow/log"
fi

# ensure the keys got removed again afterwards
SSH='ssh -n -oBatchMode=yes -oConnectTimeout=5'
${SSH} "${CYLC_TEST_HOST}" \
    LANG=C find "cylc-run/${WORKFLOW_NAME}" -type f -name "*key*"|awk -F/ '{print $NF}'|sort >'find.out'
cmp_ok 'find.out' </dev/null

purge
exit
