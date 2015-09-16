#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
set_test_number 5
mock_smtpd_init
OPT_SET=
if [[ "${TEST_NAME_BASE}" == *-globalcfg ]]; then
    mkdir 'conf'
    cat >'conf/global.rc' <<__GLOBALCFG__
[task events]
    mail events = failed, retry, succeeded
    mail smtp = ${TEST_SMTPD_HOST}
__GLOBALCFG__
    export CYLC_CONF_PATH="${PWD}/conf"
    OPT_SET='-s GLOBALCFG=True'
else
    OPT_SET="-s MAIL_SMTP=${TEST_SMTPD_HOST}"
fi

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate ${OPT_SET} "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug ${OPT_SET} "${SUITE_NAME}"

grep_ok 'Subject: \[1 task(s) retry\]' "${TEST_SMTPD_LOG}"
grep_ok 'Subject: \[1 task(s) succeeded\]' "${TEST_SMTPD_LOG}"
grep_ok '^1/t1/\(01: retry\|02: succeeded\)' "${TEST_SMTPD_LOG}"

purge_suite "${SUITE_NAME}"
mock_smtpd_kill
exit
