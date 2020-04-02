#!/bin/bash
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
# Test event mail, 2 different task events
. "$(dirname "$0")/test_header"
if ! command -v mail 2>'/dev/null'; then
    skip_all '"mail" command not available'
fi
set_test_number 5
mock_smtpd_init
OPT_SET=
if [[ "${TEST_NAME_BASE}" == *-globalcfg ]]; then
    create_test_globalrc "" "
[cylc]
    [[events]]
        mail footer = see: http://localhost/stuff/%(owner)s/%(suite)s/
[task events]
    mail events = failed, retry, succeeded
    mail smtp = ${TEST_SMTPD_HOST}"
    OPT_SET='-s GLOBALCFG=True'
else
    OPT_SET="-s MAIL_SMTP=${TEST_SMTPD_HOST}"
fi

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate ${OPT_SET} "${SUITE_NAME}"
# shellcheck disable=SC2086
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach ${OPT_SET} "${SUITE_NAME}"

contains_ok "${TEST_SMTPD_LOG}" <<__LOG__
b'retry: 1/t1/01'
b'succeeded: 1/t1/02'
b'see: http://localhost/stuff/${USER}/${SUITE_NAME}/'
__LOG__
run_ok "${TEST_NAME_BASE}-grep-log" \
    grep -q "Subject: \\[1/t1/01 retry\\].* ${SUITE_NAME}" "${TEST_SMTPD_LOG}"
run_ok "${TEST_NAME_BASE}-grep-log" \
    grep -q "Subject: \\[1/t1/02 succeeded\\].* ${SUITE_NAME}" "${TEST_SMTPD_LOG}"

purge_suite "${SUITE_NAME}"
mock_smtpd_kill
exit
