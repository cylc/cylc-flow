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
# Test event mail, single task event
. "$(dirname "$0")/test_header"
if ! command -v mail 2>'/dev/null'; then
    skip_all '"mail" command not available'
fi
set_test_number 4

mock_smtpd_init
create_test_global_config "
[scheduler]
    [[mail]]
        smtp = ${TEST_SMTPD_HOST}
"

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "$WORKFLOW_NAME"
# shellcheck disable=SC2086
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach "$WORKFLOW_NAME"


contains_ok "${TEST_SMTPD_LOG}" <<__LOG__
retry: 1/t1/01
see: http://localhost/stuff/${USER}/${WORKFLOW_NAME}/
__LOG__

run_ok "${TEST_NAME_BASE}-grep-log" \
    grep -qPizo "Subject: \[1/t1/01 retry\]\n ${WORKFLOW_NAME}" "${TEST_SMTPD_LOG}"

purge
mock_smtpd_kill
exit
