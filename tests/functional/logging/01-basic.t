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
# Test start/restart/reload config logs are created correctly

. "$(dirname "$0")/test_header"
set_test_number 7
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    [[events]]
        abort on stall timeout = true
        stall timeout = PT0S
        abort on inactivity timeout = true
        inactivity timeout = PT1M
[scheduling]
    [[graph]]
        R1 = reloader1 => stopper => reloader2
[runtime]
    [[reloader1, reloader2]]
        script = """
            cylc reload "${CYLC_WORKFLOW_ID}"
            # wait for the command to complete
            cylc__job__poll_grep_workflow_log 'Reload completed'
        """
    [[stopper]]
        script = cylc stop --now --now "${CYLC_WORKFLOW_ID}"
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach "${WORKFLOW_NAME}"

# Check scheduler logs.
ls "${WORKFLOW_RUN_DIR}/log/scheduler/" > schd_1.out
cmp_ok schd_1.out << __EOF__
01-start-01.log
log
__EOF__

# Check config logs.
ls "${WORKFLOW_RUN_DIR}/log/config/" > conf_1.out
cmp_ok conf_1.out << __EOF__
01-start-01.cylc
02-reload-01.cylc
flow-processed.cylc
__EOF__

mv "$WORKFLOW_RUN_DIR/cylc.flow.main_loop.log_db.sql" "$WORKFLOW_RUN_DIR/01.cylc.flow.main_loop.log_db.sql"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach "${WORKFLOW_NAME}"

ls "${WORKFLOW_RUN_DIR}/log/scheduler/" > schd_2.out
cmp_ok schd_2.out << __EOF__
01-start-01.log
02-restart-02.log
log
__EOF__

ls "${WORKFLOW_RUN_DIR}/log/config/" > conf_2.out
cmp_ok conf_2.out << __EOF__
01-start-01.cylc
02-reload-01.cylc
03-restart-02.cylc
04-reload-02.cylc
flow-processed.cylc
__EOF__

purge
