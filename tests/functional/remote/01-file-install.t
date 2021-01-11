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
# File install tests
export REQUIRE_PLATFORM='loc:remote comms:tcp'
. "$(dirname "$0")/test_header"
set_test_number 8

# Test configured files/directories along with default files/directories
# (app, bin, etc, lib) are correctly installed on the remote platform.

install_suite "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}" \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'"
suite_run_ok "${TEST_NAME_BASE}-run1" cylc run "${SUITE_NAME}" \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'"
RRUND="cylc-run/${SUITE_NAME}"
poll_grep_suite_log 'Holding all waiting or queued tasks now'
SSH="$(cylc get-global-config -i "[platforms][$CYLC_TEST_PLATFORM]ssh command")"
${SSH} "${CYLC_TEST_HOST}" \
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
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'" \
    -s "SECOND_RUN='${SECOND_RUN}'"
suite_run_ok "${TEST_NAME_BASE}-run2" cylc run "${SUITE_NAME}" \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'" \
    -s "SECOND_RUN='${SECOND_RUN}'"
poll_grep_suite_log 'Holding all waiting or queued tasks now'
${SSH} "${CYLC_TEST_HOST}" \
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

# Test file install completes before dependent tasks are executed
create_test_global_config "" "
[platforms]
    [[cinderella]]
        hosts = ${CYLC_TEST_HOST}
        install target = ${CYLC_TEST_INSTALL_TARGET}
    "

init_suite "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    install = dir1/, dir2/
    [[events]]
        abort on stalled = true
        abort on inactivity = true
[scheduling]
    [[graph]]
        R1 = setup => olaf => sven
[runtime]
    [[setup]]
    # This task generates a large file, ready for the file install. The aim is
    # to slow rsync and ensure tasks do not start until file install has
    # completed.
        platform = localhost
        script = """
    for DIR in "dir1" "dir2"
    do
        mkdir -p "${CYLC_SUITE_RUN_DIR}/${DIR}"
        xfs_mkfile 1024m "${CYLC_SUITE_RUN_DIR}/${DIR}/moo"
    done
    """

    [[olaf]]
        # task dependent on file install already being complete
        script = cat ${CYLC_SUITE_RUN_DIR}/dir1/moo
        platform = cinderella

    [[sven]]
        # task dependent on file install already being complete
        script = rm -r ${CYLC_SUITE_RUN_DIR}/dir1 ${CYLC_SUITE_RUN_DIR}/dir2
        platform = cinderella

__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"
purge
exit
