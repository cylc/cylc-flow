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
# test file installation to remote platforms

export REQUIRE_PLATFORM='loc:remote comms:?(tcp|ssh)'
. "$(dirname "$0")/test_header"
set_test_number 8

create_files () {
    # dump some files into the run dir
    for DIR in "bin" "app" "etc" "lib" "dir1" "dir2"
    do
        mkdir -p "${WORKFLOW_RUN_DIR}/${DIR}"
        touch "${WORKFLOW_RUN_DIR}/${DIR}/moo"
    done
    for FILE in "file1" "file2"
    do
        touch "${WORKFLOW_RUN_DIR}/${FILE}"
    done
}

# Test configured files/directories along with default files/directories
# (app, bin, etc, lib) are correctly installed on the remote platform.
TEST_NAME="${TEST_NAME_BASE}-default-paths"
init_workflow "${TEST_NAME}" <<__FLOW_CONFIG__
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        platform = $CYLC_TEST_PLATFORM
__FLOW_CONFIG__
RUN_DIR_REL="${WORKFLOW_RUN_DIR#$HOME/}"

create_files

# run the flow
run_ok "${TEST_NAME}-validate" cylc validate "${WORKFLOW_NAME}" \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'"
workflow_run_ok "${TEST_NAME}-run1" cylc play "${WORKFLOW_NAME}" \
    --no-detach \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'"

# ensure these files get installed on the remote platform
SSH="$(cylc config -d -i "[platforms][$CYLC_TEST_PLATFORM]ssh command")"
${SSH} "${CYLC_TEST_HOST}" \
    find "${RUN_DIR_REL}/"{app,bin,etc,lib} -type f | sort > 'find.out'
cmp_ok 'find.out'  <<__OUT__
${RUN_DIR_REL}/app/moo
${RUN_DIR_REL}/bin/moo
${RUN_DIR_REL}/etc/moo
${RUN_DIR_REL}/lib/moo
__OUT__

purge
# -----------------------------------------------------------------------------

# Test the [scheduler]install configuration
TEST_NAME="${TEST_NAME_BASE}-configured-paths"
init_workflow "${TEST_NAME}" <<__FLOW_CONFIG__
[scheduler]
    install = dir1/, dir2/, file1, file2
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        platform = $CYLC_TEST_PLATFORM
__FLOW_CONFIG__
RUN_DIR_REL="${WORKFLOW_RUN_DIR#$HOME/}"

create_files

run_ok "${TEST_NAME}-validate" cylc validate "${WORKFLOW_NAME}" \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'"
workflow_run_ok "${TEST_NAME}-run2" cylc play "${WORKFLOW_NAME}" \
    --no-detach \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'"

${SSH} "${CYLC_TEST_HOST}" \
    find "${RUN_DIR_REL}/"{app,bin,dir1,dir2,file1,file2,etc,lib} -type f | sort > 'find.out'
cmp_ok 'find.out'  <<__OUT__
${RUN_DIR_REL}/app/moo
${RUN_DIR_REL}/bin/moo
${RUN_DIR_REL}/dir1/moo
${RUN_DIR_REL}/dir2/moo
${RUN_DIR_REL}/etc/moo
${RUN_DIR_REL}/file1
${RUN_DIR_REL}/file2
${RUN_DIR_REL}/lib/moo
__OUT__

purge
# -----------------------------------------------------------------------------

if ! command -v xfs_mkfile; then
    skip 2 "xfs_mkfile not installed"
    exit
fi

# Test file install completes before dependent tasks are executed
TEST_NAME="${TEST_NAME_BASE}-installation-timing"
init_workflow "${TEST_NAME}" <<__FLOW_CONFIG__
[scheduler]
    install = dir1/, dir2/
    [[events]]
        abort on stall = true
        abort on inactivity = true

[scheduling]
    [[graph]]
        R1 = olaf => sven

[runtime]
    [[olaf]]
        # task dependent on file install already being complete
        script = cat \${CYLC_WORKFLOW_RUN_DIR}/dir1/moo
        platform = $CYLC_TEST_PLATFORM

    [[sven]]
        # task dependent on file install already being complete
        script = rm -r \${CYLC_WORKFLOW_RUN_DIR}/dir1 \${CYLC_WORKFLOW_RUN_DIR}/dir2
        platform = $CYLC_TEST_PLATFORM

__FLOW_CONFIG__

# This generates a large file, ready for the file install. The aim is
# to slow rsync and ensure tasks do not start until file install has
# completed.
for DIR in "dir1" "dir2"; do
    mkdir -p "${WORKFLOW_RUN_DIR}/${DIR}"
    xfs_mkfile 1024m "${WORKFLOW_RUN_DIR}/${DIR}/moo"
done

run_ok "${TEST_NAME}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

purge
exit
