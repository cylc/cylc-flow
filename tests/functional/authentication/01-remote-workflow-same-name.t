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
# Test communication from a remote host (non-shared file system) when it has
# a workflow with the same name registered, but not running. (Obviously, it will
# be very confused if it is running under its ~/cylc-run/WORKFLOW as well.)
export REQUIRE_PLATFORM='loc:remote fs:indep'
. "$(dirname "$0")/test_header"
set_test_number 3

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

SSH_OPTS='-oBatchMode=yes -oConnectTimeout=5'
# shellcheck disable=SC2029,SC2086
#ssh ${SSH_OPTS} "${CYLC_TEST_HOST}" mkdir -p "cylctb-cylc-source/${WORKFLOW_NAME}"
SRC_DIR="$(ssh ${SSH_OPTS} "${CYLC_TEST_HOST}" mktemp -d)"
# shellcheck disable=SC2086
scp ${SSH_OPTS} -pqr "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/"* \
    "${CYLC_TEST_HOST}:${SRC_DIR}"
# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-install" \
    ssh ${SSH_OPTS} "${CYLC_TEST_HOST}" bash -lc \
    "CYLC_VERSION=$(cylc version) cylc install ${SRC_DIR} --workflow-name=${WORKFLOW_NAME} --no-run-name"

workflow_run_ok "${TEST_NAME_BASE}" \
    cylc play --debug --no-detach --reference-test "${WORKFLOW_NAME}"

purge
exit
