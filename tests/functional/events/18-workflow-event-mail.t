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
# Test event mail.
. "$(dirname "$0")/test_header"
if ! command -v mail 2>'/dev/null'; then
    skip_all '"mail" command not available'
fi
set_test_number 3
mock_smtpd_init
OPT_SET=
if [[ "${TEST_NAME_BASE}" == *-globalcfg ]]; then
    create_test_global_config "" "
[scheduler]
    [[events]]
        mail events = startup, shutdown
    [[mail]]
        footer = see: http://localhost/stuff/%(owner)s/%(workflow)s/
        smtp = ${TEST_SMTPD_HOST}"
    OPT_SET='-s GLOBALCFG=True'
else
    create_test_global_config "
[scheduler]
    [[mail]]
        smtp = ${TEST_SMTPD_HOST}
"
fi

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate ${OPT_SET} "${WORKFLOW_NAME}"
# shellcheck disable=SC2086
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach ${OPT_SET} "${WORKFLOW_NAME}"

contains_ok "${TEST_SMTPD_LOG}" <<__LOG__
event: startup
message: workflow starting
event: shutdown
message: AUTOMATIC
see: http://localhost/stuff/${USER}/${WORKFLOW_NAME}/
__LOG__

purge
mock_smtpd_kill
exit
