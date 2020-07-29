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
# Test custom task event handler bad template
. "$(dirname "$0")/test_header"
set_test_number 4

if [[ "${TEST_NAME_BASE}" == *-globalcfg ]]; then
    create_test_globalrc '' ''
fi
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_fail "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
cmp_ok "${TEST_NAME_BASE}-validate.stderr" <<'__ERR__'
SuiteConfigError: bad task event handler template t1: echo %(rubbish)s: KeyError('rubbish')
__ERR__
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
LOG="${SUITE_RUN_DIR}/log/suite/log"
run_ok "${TEST_NAME_BASE}-log" grep -q -F "ERROR - 1/t1/01 ('event-handler-00', 'succeeded') bad template: 'rubbish'" "${LOG}"

purge_suite "${SUITE_NAME}"
exit
