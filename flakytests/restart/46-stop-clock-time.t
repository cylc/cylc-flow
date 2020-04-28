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
# Test restart with stop clock time

. "$(dirname "$0")/test_header"

dumpdbtables() {
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT * FROM suite_params WHERE key=="stop_clock_time";' \
        >'stopclocktime.out'
}

set_test_number 6

# Event should look like this:
# Start suite
# At t1.1, set stop clock time to 60 seconds ahead
# At t2.1, stop suite
# Restart
# Suite runs to stop clock time, reset stop clock time
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    [[parameters]]
        i = 1..10
    [[events]]
        abort on stalled = True
        abort on inactivity = True
        inactivity = P2M
[scheduling]
    [[graph]]
        R1 = t<i-1> => t<i>
[runtime]
    [[t<i>]]
        script = sleep 10
    [[t<i=1>]]
        script = """
CLOCKTIME="$(($(date +%s) + 60))"
echo "${CLOCKTIME}" >"${CYLC_SUITE_RUN_DIR}/clocktime"
cylc stop -w "$(date --date="@${CLOCKTIME}" +%FT%T%:z)" "${CYLC_SUITE_NAME}"
"""
    [[t<i=2>]]
        script = cylc stop "${CYLC_SUITE_NAME}"
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}" --no-detach
read -r CLOCKTIME <"${SUITE_RUN_DIR}/clocktime"
dumpdbtables
cmp_ok 'stopclocktime.out' <<<"stop_clock_time|${CLOCKTIME}"

suite_run_ok "${TEST_NAME_BASE}-restart-1" \
    cylc restart "${SUITE_NAME}" --no-detach
dumpdbtables
cmp_ok 'stopclocktime.out' <'/dev/null'
cut -d ' ' -f 4- "${SUITE_RUN_DIR}/log/suite/log" >'log.edited'
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
    ST_FILE="${SUITE_RUN_DIR}/log/job/1/t_i${i}/01/job.status"
    if [[ -e "${ST_FILE}" ]]; then
        JOB_ID="$(awk -F= '$1 == "CYLC_BATCH_SYS_JOB_ID" {print $2}' "${ST_FILE}")"
        poll_pid_done "${JOB_ID}"
    fi
done

purge_suite "${SUITE_NAME}"
exit
