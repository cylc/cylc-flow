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
# Test sending commands to a workflow on a host with shared file system with
# current host.
export REQUIRE_PLATFORM='loc:remote fs:shared'
. "$(dirname "$0")/test_header"
set_test_number 4

# "install_workflow" does not work here because it installs workflows on the TMPDIR,
# which is often on local file systems. We need to ensure that the workflow
# definition directory is on a shared file system.
WORKFLOW_NAME="${CYLC_TEST_REG_BASE}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}"
WORKFLOW_RUN_DIR="$RUN_DIR/${WORKFLOW_NAME}"
mkdir -p "$(dirname "${WORKFLOW_RUN_DIR}")"
cp -r "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}" "${WORKFLOW_RUN_DIR}"
cylc install --workflow-name="${WORKFLOW_NAME}" --no-run-name 2>'/dev/null'

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

cylc play --debug --no-detach --reference-test \
    --host="${CYLC_TEST_HOST}" "${WORKFLOW_NAME}" 1>'out' 2>&1 &
WORKFLOW_PID="$!"

# Poll for job to fail
WORKFLOW_LOG="${WORKFLOW_RUN_DIR}/log/scheduler/log"
# Note: double poll existence of workflow log on workflow host and then localhost to
# avoid any issues with unstable mounting of the shared file system.
poll ssh -oBatchMode=yes -n "${CYLC_TEST_HOST}" test -e "${WORKFLOW_LOG}"
poll_grep_workflow_log -E '19700101T0000Z/t1/01:submitted.* => running'
poll_grep_workflow_log -E '19700101T0000Z/t1/01:running.* => failed'

run_ok "${TEST_NAME_BASE}-broadcast" \
    cylc broadcast -n 't1' -s '[environment]CYLC_TEST_VAR_FOO=foo' "${WORKFLOW_NAME}"
run_ok "${TEST_NAME_BASE}-trigger" \
    cylc trigger "${WORKFLOW_NAME}//19700101T0000Z/t1"

if wait "${WORKFLOW_PID}"; then
    ok "${TEST_NAME_BASE}-run"
else
    fail "${TEST_NAME_BASE}-run"
    cat 'out' >&2
fi

purge
exit
