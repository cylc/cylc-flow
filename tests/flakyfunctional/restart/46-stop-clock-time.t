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
# Test restart with stop clock time

. "$(dirname "$0")/test_header"

dumpdbtables() {
    sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
        "SELECT * FROM workflow_params WHERE key=='stop_clock_time';" \
        >'stopclocktime.out'
}

set_test_number 6

# Event should look like this:
# Start workflow
# At 1/t1, set stop clock time to 60 seconds ahead
# At 1/t2, stop workflow
# Restart
# Workflow runs to stop clock time, reset stop clock time
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[task parameters]
    i = 1..10
[scheduler]
    [[events]]
        abort on stall timeout = True
        stall timeout = PT0S
        abort on inactivity timeout = True
        inactivity timeout = P2M
[scheduling]
    [[graph]]
        R1 = t<i-1> => t<i>
[runtime]
    [[t<i>]]
        script = sleep 10
    [[t<i=1>]]
        script = """
CLOCKTIME="$(($(date +%s) + 60))"
echo "${CLOCKTIME}" >"${CYLC_WORKFLOW_RUN_DIR}/clocktime"
cylc stop -w "$(date --date="@${CLOCKTIME}" +%FT%T%:z)" "${CYLC_WORKFLOW_ID}"
"""
    [[t<i=2>]]
        script = cylc stop "${CYLC_WORKFLOW_ID}"
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --no-detach
read -r CLOCKTIME <"${WORKFLOW_RUN_DIR}/clocktime"
dumpdbtables
cmp_ok 'stopclocktime.out' <<<"stop_clock_time|${CLOCKTIME}"

workflow_run_ok "${TEST_NAME_BASE}-restart-1" \
    cylc play "${WORKFLOW_NAME}" --no-detach
dumpdbtables
cmp_ok 'stopclocktime.out' <<<"stop_clock_time|"
cut -d ' ' -f 4- "${WORKFLOW_RUN_DIR}/log/scheduler/log" >'log.edited'
if [[ "$(date +%:z)" == '+00:00' ]]; then
    CLOCKTIMESTR="$(date --date="@${CLOCKTIME}" +%FT%TZ)"
else
    CLOCKTIMESTR="$(date --date="@${CLOCKTIME}" +%FT%T%:z)"
fi
contains_ok 'log.edited' <<__LOG__
+ stop clock time = ${CLOCKTIME} (${CLOCKTIMESTR})
Wall clock stop time reached: ${CLOCKTIMESTR}
__LOG__

for i in {01..10}; do
    ST_FILE="${WORKFLOW_RUN_DIR}/log/job/1/t_i${i}/01/job.status"
    if [[ -e "${ST_FILE}" ]]; then
        JOB_ID="$(awk -F= '$1 == "CYLC_JOB_ID" {print $2}' "${ST_FILE}")"
        poll_pid_done "${JOB_ID}"
    fi
done

purge
exit
