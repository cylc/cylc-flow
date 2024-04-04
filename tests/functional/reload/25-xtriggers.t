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

# Ensure that xtriggers are preserved after reloads
# See https://github.com/cylc/cylc-flow/issues/4866

. "$(dirname "$0")/test_header"

set_test_number 6

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduling]
    [[graph]]
        R1 = """
            broken
            reload
        """

[runtime]
    [[broken]]
        script = false
        # should be long enough for the reload to complete
        # (annoyingly we can't make this event driven)
        execution retry delays = PT1M
        # NOTE: "execution retry delays" is implemented as an xtrigger

    [[reload]]
        script = """
            # wait for "broken" to fail
            cylc__job__poll_grep_workflow_log -E '1/broken/01.* \(received\)failed/ERR'
            # fix "broken" to allow it to pass
            sed -i 's/false/true/' "${CYLC_WORKFLOW_RUN_DIR}/flow.cylc"
            # reload the workflow
            cylc reload "${CYLC_WORKFLOW_ID}"
        """
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-val" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --no-detach -v

# ensure the following order of events
# 1. "1/broken" fails
# 2. workflow is reloaded (by "1/reload")
# 3. the retry xtrigger for "1/broken" becomes satisfied (after the reload)
#    (thus proving that the xtrigger survived the reload)
# 4. "1/broken" succeeds

log_scan "${TEST_NAME_BASE}-scan" \
    "$(cylc cat-log -m p "${WORKFLOW_NAME}")" \
    1 1 \
    '1/broken.* (received)failed/ERR'

log_scan "${TEST_NAME_BASE}-scan" \
    "$(cylc cat-log -m p "${WORKFLOW_NAME}")" 1 1 \
    'Command "reload_workflow" actioned' \

log_scan "${TEST_NAME_BASE}-scan" \
    "$(cylc cat-log -m p "${WORKFLOW_NAME}")" \
    1 1 \
    'xtrigger satisfied: _cylc_retry_1/broken' \
    '1/broken.* => succeeded'

purge
