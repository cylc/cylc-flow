#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
# Test cache of passphrase for a suite running on a remote host with no shared
# HOME file system, but with non-interactive SSH access.
# This test assumes compatible version of cylc is available on the configured
# remote host.
. "$(dirname "$0")/test_header"

export CYLC_TEST_HOST=$( \
    cylc get-global-config -i '[test battery]remote host' 2>'/dev/null')
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip_all '"[test battery]remote host": not defined'
fi
set_test_number 5

SSH_OPTS='-oBatchMode=yes -oConnectTimeout=5'
HOST_WORK_DIR="$( \
    ssh ${SSH_OPTS} -n "${CYLC_TEST_HOST}" \
    'mktemp -d --tmpdir="${HOME}/cylc-run" ctb-XXXXXXXX')"
scp ${SSH_OPTS} -pqr "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/"* \
    "${CYLC_TEST_HOST}:${HOST_WORK_DIR}"

SUITE_NAME="$(basename "${HOST_WORK_DIR}")"
cylc unregister "${SUITE_NAME}" 2>'/dev/null' || true
cylc register --host="${CYLC_TEST_HOST}" "${SUITE_NAME}" "${HOST_WORK_DIR}"
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate --host="${CYLC_TEST_HOST}" "${SUITE_NAME}"

cylc run --debug --host="${CYLC_TEST_HOST}" --reference-test "${SUITE_NAME}" \
    1>'out' 2>'err' &
SUITE_PID=$!

# Wait until the task failed
poll '!' grep -q 't1.19700101T0000Z.*failed' 'err'

run_ok "${TEST_NAME_BASE}-broadcast" \
    cylc broadcast --host="${CYLC_TEST_HOST}" "${SUITE_NAME}" \
    -n 't1' -p '1970' -s '[environment]FOO=foo'

run_ok "${TEST_NAME_BASE}-trigger" \
    cylc trigger --host="${CYLC_TEST_HOST}" "${SUITE_NAME}" '*:failed'

# Check that we have cached the passphrase
CACHED="${HOME}/.cylc/passphrases/${USER}@${CYLC_TEST_HOST}/${SUITE_NAME}"
exists_ok "${CACHED}/passphrase"

run_ok "${TEST_NAME_BASE}" wait "${SUITE_PID}"

cylc unregister --host="${CYLC_TEST_HOST}" "${SUITE_NAME}"
ssh ${SSH_OPTS} -n "${CYLC_TEST_HOST}" "rm -fr '${HOST_WORK_DIR}'" >&2
rm -fr "${CACHED}"
rmdir "${HOME}/.cylc/passphrases/${USER}@${CYLC_TEST_HOST}" 2>'/dev/null' \
    || true

exit
