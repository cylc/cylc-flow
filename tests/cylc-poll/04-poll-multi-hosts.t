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
# Test poll multiple jobs on localhost and a remote host
. "$(dirname "$0")/test_header"
export CYLC_TEST_HOST=$( \
    cylc get-global-config -i '[test battery]remote host' 2>'/dev/null')
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip_all '"[test battery]remote host": not defined'
fi

set_test_number 3

export CYLC_CONF_PATH=
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
set -eu
SSH='ssh -oBatchMode=yes -oConnectTimeout=5'
${SSH} "${CYLC_TEST_HOST}" \
    "mkdir -p .cylc/${SUITE_NAME}/ && cat >.cylc/${SUITE_NAME}/passphrase" \
    <"${TEST_DIR}/${SUITE_NAME}/passphrase"
set +eu

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}" -s "CYLC_TEST_HOST=${CYLC_TEST_HOST}"

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug "${SUITE_NAME}" \
    -s "CYLC_TEST_HOST=${CYLC_TEST_HOST}"

RUN_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
LOG="${RUN_DIR}/log/suite/log"
sed -n 's/^.*\(cylc jobs-poll\)/\1/p' "${LOG}" | sort >'edited-suite-log'

sort >'edited-suite-log-ref' <<__LOG__
cylc jobs-poll --debug --host=${CYLC_TEST_HOST} -- '\$HOME/cylc-run/${SUITE_NAME}/log/job' 1/remote-fail-1/01 1/remote-success-1/01 1/remote-success-2/01
cylc jobs-poll --debug -- ${RUN_DIR}/log/job 1/local-fail-1/01 1/local-fail-2/01 1/local-success-1/01
__LOG__
cmp_ok 'edited-suite-log' 'edited-suite-log-ref'

$SSH -n "$CYLC_TEST_HOST" "rm -rf '.cylc/$SUITE_NAME' 'cylc-run/$SUITE_NAME'"
purge_suite "${SUITE_NAME}"
exit
