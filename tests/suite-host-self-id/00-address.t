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
# Ensure that suite contact env host IP address is defined

. "$(dirname "$0")/test_header"
set_test_number 2
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

#-------------------------------------------------------------------------------
MY_INET_TARGET=$( \
    cylc get-global-config '--item=[suite host self-identification]target')
MY_HOST_IP=$(python -m cylc.suite_host "${MY_INET_TARGET}")

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}" "--set=MY_HOST_IP=${MY_HOST_IP}"

mkdir 'conf'
cat >'conf/global.rc' <<'__GLOBALCFG__'
[suite host self-identification]
    method = address
__GLOBALCFG__
export CYLC_CONF_PATH="${PWD}/conf"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug "${SUITE_NAME}" \
    "--set=MY_HOST_IP=${MY_HOST_IP}"
#-------------------------------------------------------------------------------

purge_suite "${SUITE_NAME}"
exit
