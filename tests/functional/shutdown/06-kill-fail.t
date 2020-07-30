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
# Test kill command fail on shutdown --kill.
. "$(dirname "$0")/test_header"

set_test_number 3

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"
LOGD="$RUN_DIR/${SUITE_NAME}/log/job"
JLOGD="${LOGD}/1/t1/01"
poll_grep 'CYLC_JOB_INIT_TIME' "${JLOGD}/job.status"
mv "${JLOGD}/job.status" "${JLOGD}/job.status.old"
run_ok "${TEST_NAME_BASE}-shutdown" \
    cylc shutdown --kill --max-polls=10 --interval=2 "${SUITE_NAME}"
mv "${JLOGD}/job.status.old" "${JLOGD}/job.status"
cylc jobs-kill "${LOGD}" '1/t1/01' 1>'/dev/null' 2>&1
purge_suite "${SUITE_NAME}"
exit
