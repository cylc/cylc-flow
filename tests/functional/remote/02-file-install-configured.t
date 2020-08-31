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
# Checks default files (app, bin, etc, lib) are correctly installed on the
# remote platform.

export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
require_remote_platform
set_test_number 3

init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
#!jinja2
[cylc]
[scheduler]
        includes = dir1/, dir2/, file1, file2
[scheduling]
    [[graph]]
        R1 = startup => holder => held
[runtime]
    [[startup]]
        script = """
    for DIR in "dir1" "dir2"
    do
        mkdir -p "${CYLC_SUITE_RUN_DIR}/${DIR}"
        touch "${CYLC_SUITE_RUN_DIR}/${DIR}/moo"
    done
    
    for FILE in "file1" "file2"
    do
        touch "${CYLC_SUITE_RUN_DIR}/${FILE}"
    done
    """
        platform = localhost
    [[holder]]
        script = """cylc hold "${CYLC_SUITE_NAME}" """
        platform = {{CYLC_TEST_PLATFORM}}
    [[held]]
        script = true
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}" \
    -s "CYLC_TEST_PLATFORM=${CYLC_TEST_PLATFORM}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}" \
    -s "CYLC_TEST_PLATFORM=${CYLC_TEST_PLATFORM}"
RRUND="cylc-run/${SUITE_NAME}"
poll_grep_suite_log 'Holding all waiting or queued tasks now'
SSH='ssh -n -oBatchMode=yes -oConnectTimeout=10' 
${SSH} "${CYLC_TEST_PLATFORM}" \
find "${RRUND}/"{dir1,dir2,file1,file2} -type f | sort > 'find.out'
cmp_ok 'find.out'  <<__OUT__
${RRUND}/dir1/moo
${RRUND}/dir2/moo
${RRUND}/file1
${RRUND}/file2
__OUT__

cylc stop --max-polls=60 --interval=1 "${SUITE_NAME}"
purge_suite_platform "${CYLC_TEST_PLATFORM}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
