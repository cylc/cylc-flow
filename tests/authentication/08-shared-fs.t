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
# Test sending commands to a suite on a host with shared file system with
# current host.
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"

CYLC_TEST_HOST="$( \
    cylc get-global-config -i '[test battery]remote host with shared fs' \
    2>'/dev/null')"
export CYLC_TEST_HOST
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip_all '"[test battery]remote host with shared fs": not defined'
fi
set_test_number 4

# "install_suite" does not work here because it installs suites on the TMPDIR,
# which is often on local file systems. We need to ensure that the suite
# definition directory is on a shared file system.
SUITE_NAME="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}"
SUITE_RUN_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
mkdir -p "$(dirname "${SUITE_RUN_DIR}")"
cp -r "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}" "${SUITE_RUN_DIR}"
cylc register "${SUITE_NAME}" "${SUITE_RUN_DIR}" 2>'/dev/null'

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

cylc run --debug --no-detach --reference-test --host="${CYLC_TEST_HOST}" "${SUITE_NAME}" \
    1>'out' 2>&1 &
SUITE_PID="$!"

# Poll for job to fail
SUITE_LOG="${SUITE_RUN_DIR}/log/suite/log"
# Note: double poll existence of suite log on suite host and then localhost to
# avoid any issues with unstable mounting of the shared file system.
poll ssh -oBatchMode=yes -n "${CYLC_TEST_HOST}" test -e "${SUITE_LOG}"
poll_grep_suite_log -F '[t1.19700101T0000Z] -submitted => running'
poll_grep_suite_log -F '[t1.19700101T0000Z] -running => failed'

run_ok "${TEST_NAME_BASE}-broadcast" \
    cylc broadcast -n 't1' -s '[environment]CYLC_TEST_VAR_FOO=foo' "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-trigger" \
    cylc trigger "${SUITE_NAME}" 't1' '19700101T0000Z'

if wait "${SUITE_PID}"; then
    ok "${TEST_NAME_BASE}-run"
else
    fail "${TEST_NAME_BASE}-run"
    cat 'out' >&2
fi

purge_suite "${SUITE_NAME}"
exit
