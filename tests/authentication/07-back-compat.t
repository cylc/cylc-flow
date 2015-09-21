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

# Test authentication - ignore old clients, report new bad clients.

. $(dirname $0)/test_header
set_test_number 11

# Set things up and run the suite.
install_suite "${TEST_NAME_BASE}" basic
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
cylc run "${SUITE_NAME}"

# Scan to grab the suite's port.
TEST_NAME="${TEST_NAME_BASE}-new-scan"
cylc scan -fb -n "${SUITE_NAME}" localhost > scan.out
run_ok "${TEST_NAME}" sed -n "s/.*@localhost:\([0-9][0-9]*\)/\1/gp" scan.out
PORT=$(<"${TEST_NAME}.stdout")

# Simulate an old client.
ERR_PATH="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/log/suite/err"
TEST_NAME="${TEST_NAME_BASE}-old-client-snapshot-err"
run_ok "${TEST_NAME}" cp "${ERR_PATH}" err-before-scan
TEST_NAME="${TEST_NAME_BASE}-old-client-simulate"
run_fail "${TEST_NAME}" python -c "
import sys
import Pyro.core
uri = 'PYROLOC://localhost:' + sys.argv[1] + '/cylcid'
proxy = Pyro.core.getProxyForURI(uri)
proxy._setIdentification('0123456789abcdef')
name, owner = proxy.id()" "${PORT}"
grep_ok "ConnectionDeniedError" "${TEST_NAME}.stderr"

# Check that the old client connection is not logged.
# Get any new lines added to the error file.
comm -13 err-before-scan "${ERR_PATH}" >"${TEST_NAME_BASE}-old-client-err-diff"
TEST_NAME="${TEST_NAME_BASE}-log-old-client"
run_fail "${TEST_NAME}" grep "WARNING - \[client-connect\] DENIED" \
    "${TEST_NAME_BASE}-old-client-err-diff"

# Simulate a new, suspicious client.
TEST_NAME="${TEST_NAME_BASE}-new-bad-client-snapshot-err"
run_ok "${TEST_NAME}" cp "${ERR_PATH}" err-before-scan
TEST_NAME="${TEST_NAME_BASE}-new-bad-client-simulate"
run_fail "${TEST_NAME}" python -c '
import sys
import Pyro.core, Pyro.protocol

class MyConnValidator(Pyro.protocol.DefaultConnValidator):

    """Create an incorrect but plausible auth token."""

    def createAuthToken(self, authid, challenge, peeraddr, URI, daemon):
        return "colonel_mustard:drawing_room:dagger:mystery:57abbed"

uri = "PYROLOC://localhost:" + sys.argv[1] + "/cylcid"
proxy = Pyro.core.getProxyForURI(uri)
proxy._setNewConnectionValidator(MyConnValidator())
proxy._setIdentification("0123456789abcdef")
proxy.identify()' "${PORT}"
grep_ok "ConnectionDeniedError" "${TEST_NAME}.stderr"

# Check that the new client connection failure is logged (it is suspicious).
TEST_NAME="${TEST_NAME_BASE}-log-new-client"
# Get any new lines added to the error file.
comm -13 err-before-scan "${ERR_PATH}" >"${TEST_NAME_BASE}-new-client-err-diff"
# Check the new lines for a connection denied report.
grep_ok "WARNING - \[client-connect\] DENIED colonel_mustard@drawing_room:mystery dagger$" \
    "${TEST_NAME_BASE}-new-client-err-diff"

# Shutdown and purge.
TEST_NAME="${TEST_NAME_BASE}-stop"
run_ok "${TEST_NAME}" cylc stop --max-polls=10 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
