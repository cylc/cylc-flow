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
# Checks configured files/directories along with default files/directories
# (app, bin, etc, lib) are correctly installed on the remote platform.
export REQUIRE_PLATFORM='loc:remote comms:tcp'
. "$(dirname "$0")/test_header"
set_test_number 6
install_suite "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}" \
    -s "CYLC_TEST_PLATFORM=${CYLC_TEST_PLATFORM}"
suite_run_ok "${TEST_NAME_BASE}-run1" cylc run "${SUITE_NAME}" \
    -s "CYLC_TEST_PLATFORM=${CYLC_TEST_PLATFORM}"
RRUND="cylc-run/${SUITE_NAME}"
poll_grep_suite_log 'Holding all waiting or queued tasks now'
SSH="$(cylc get-global-config -i "[platforms][$CYLC_TEST_PLATFORM]ssh command")"
${SSH} "${CYLC_TEST_PLATFORM}" \
find "${RRUND}/"{app,bin,etc,lib} -type f | sort > 'find.out'
cmp_ok 'find.out'  <<__OUT__
${RRUND}/app/moo
${RRUND}/bin/moo
${RRUND}/etc/moo
${RRUND}/lib/moo
__OUT__

cylc stop --max-polls=60 --interval=1 "${SUITE_NAME}"
purge

install_suite "${TEST_NAME_BASE}"

export SECOND_RUN="dir1/, dir2/, file1, file2"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}" \
    -s "CYLC_TEST_PLATFORM=${CYLC_TEST_PLATFORM}" -s "SECOND_RUN=${SECOND_RUN}"
suite_run_ok "${TEST_NAME_BASE}-run2" cylc run "${SUITE_NAME}" \
    -s "CYLC_TEST_PLATFORM=${CYLC_TEST_PLATFORM}" -s "SECOND_RUN=${SECOND_RUN}"
poll_grep_suite_log 'Holding all waiting or queued tasks now'
${SSH} "${CYLC_TEST_PLATFORM}" \
find "${RRUND}/"{app,bin,dir1,dir2,file1,file2,etc,lib} -type f | sort > 'find.out'
cmp_ok 'find.out'  <<__OUT__
${RRUND}/app/moo
${RRUND}/bin/moo
${RRUND}/dir1/moo
${RRUND}/dir2/moo
${RRUND}/etc/moo
${RRUND}/file1
${RRUND}/file2
${RRUND}/lib/moo
__OUT__

cylc stop --max-polls=60 --interval=1 "${SUITE_NAME}"

purge
exit
