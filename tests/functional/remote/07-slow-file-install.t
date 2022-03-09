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
# Test file install completes before dependent tasks are executed

export REQUIRE_PLATFORM='loc:remote comms:?(tcp|ssh)'
. "$(dirname "$0")/test_header"
set_test_number 2

TEST_NAME="${TEST_NAME_BASE}-installation-timing"
install_workflow "${TEST_NAME}" "${TEST_NAME_BASE}"

for DIR in "dir1" "dir2"; do
    mkdir -p "${WORKFLOW_RUN_DIR}/${DIR}"
    touch "${WORKFLOW_RUN_DIR}/${DIR}/moo"
    echo "hello" > "${WORKFLOW_RUN_DIR}/${DIR}/moo"
    cat "${WORKFLOW_RUN_DIR}/${DIR}/moo" >&2
done

run_ok "${TEST_NAME}-validate" cylc validate "${WORKFLOW_NAME}"
export PATH="${WORKFLOW_RUN_DIR}/bin:$PATH"
# shellcheck disable=SC2029
ssh -n "${CYLC_TEST_HOST}" "mkdir -p 'cylc-run/${WORKFLOW_NAME}/'"
rsync -a 'bin' "${CYLC_TEST_HOST}:cylc-run/${WORKFLOW_NAME}/"
workflow_run_ok "${TEST_NAME}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

purge
exit
