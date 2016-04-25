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

# Test authentication - ignore old client denials, report bad new clients.

. $(dirname $0)/test_header
set_test_number 23

# Set things up and run the suite.
# Choose the default global.rc hash settings, for reference.
create_test_globalrc '' '
[authentication]
    hashes = sha256,md5
    scan hash = md5'
install_suite "${TEST_NAME_BASE}" basic
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
cylc run "${SUITE_NAME}"

# Scan to grab the suite's port.
sleep 5  # Wait for the suite to initialize.
PORT=$(cylc ping -v "${SUITE_NAME}" | cut -d':' -f 2)

# Simulate an old client with the wrong passphrase.
ERR_PATH="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/log/suite/err"
TEST_NAME="${TEST_NAME_BASE}-old-client-checkpoint-err"
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

# Simulate an old client with the right passphrase.
ERR_PATH="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/log/suite/err"
TEST_NAME="${TEST_NAME_BASE}-old-client-checkpoint-ok"
run_ok "${TEST_NAME}" cp "${ERR_PATH}" err-before-scan
TEST_NAME="${TEST_NAME_BASE}-old-client-simulate-ok"
PASSPHRASE=$(cat $(cylc get-dir $SUITE_NAME)/passphrase)
run_ok "${TEST_NAME}" python -c "
import sys
import Pyro.core
uri = 'PYROLOC://localhost:' + sys.argv[1] + '"/${USER}.${SUITE_NAME}.suite-info"'
print >> sys.stderr, uri
proxy = Pyro.core.getProxyForURI(uri)
proxy._setIdentification('"$PASSPHRASE"')
info = proxy.get('get_suite_info')" "${PORT}"
grep_ok "\[client-command\] get_suite_info (user)@(host):(OLD_CLIENT) (uuid)" "$(cylc cat-log -l $SUITE_NAME)"

# Simulate a new, suspicious client.
TEST_NAME="${TEST_NAME_BASE}-new-bad-client-checkpoint-err"
run_ok "${TEST_NAME}" cp "${ERR_PATH}" err-before-scan
TEST_NAME="${TEST_NAME_BASE}-new-bad-client-simulate"
run_fail "${TEST_NAME}" python -c '
import sys
import Pyro.core, Pyro.protocol

class MyConnValidator(Pyro.protocol.DefaultConnValidator):

    """Create an incorrect but plausible auth token."""

    def createAuthToken(self, authid, challenge, peeraddr, URI, daemon):
        return "colonel_mustard:drawing_room:dagger:mystery:decea5ede57abbed"

uri = "PYROLOC://localhost:" + sys.argv[1] + "/cylcid"
proxy = Pyro.core.getProxyForURI(uri)
proxy._setNewConnectionValidator(MyConnValidator())
proxy._setIdentification("0123456789abcdef")
proxy.identify()' "${PORT}"
grep_ok "ConnectionDeniedError" "${TEST_NAME}.stderr"

# Check that the new client connection failure is logged (it is suspicious).
TEST_NAME="${TEST_NAME_BASE}-log-new-client"
# Get any new lines added to the error file.
comm -13 err-before-scan "${ERR_PATH}" >"${TEST_NAME}-new-client-err-diff"
# Check the new lines for a connection denied report.
grep_ok "WARNING - \[client-connect\] DENIED colonel_mustard@drawing_room:mystery dagger$" \
    "${TEST_NAME}-new-client-err-diff"

# Simulate a client with the wrong hash.
TEST_NAME="${TEST_NAME_BASE}-new-wrong-hash-client-checkpoint-err"
run_ok "${TEST_NAME}" cp "${ERR_PATH}" err-before-scan
create_test_globalrc '' '
[authentication]
    hashes = sha1
    scan hash = sha1'
run_ok "${TEST_NAME}" cylc scan -fb -n "${SUITE_NAME}" 'localhost'
comm -13 err-before-scan "${ERR_PATH}" >"${TEST_NAME}-diff"
# Wrong hash usage should not be logged as the hash choice may change.
cat "${TEST_NAME}-diff" >/dev/tty
diff "${TEST_NAME}-diff" - </dev/null >/dev/tty
cmp_ok "${TEST_NAME}-diff" </dev/null

# Run a scan using SHA256 hashing (default is MD5).
TEST_NAME="${TEST_NAME_BASE}-scan-sha256"
create_test_globalrc '' '
[authentication]
    scan hash = sha256'
run_ok "${TEST_NAME}" cylc scan -fb -n "${SUITE_NAME}" 'localhost'
grep_ok "${SUITE_NAME} ${USER}@localhost:${PORT}" "${TEST_NAME}.stdout"
create_test_globalrc

# Shutdown.
TEST_NAME="${TEST_NAME_BASE}-stop"
run_ok "${TEST_NAME}" cylc stop --max-polls=10 --interval=1 "${SUITE_NAME}"

# Now run an MD5 suite and see if we can trigger with a different
# default hash (SHA256), falling back to MD5.

purge_suite "${SUITE_NAME}" basic
# Set things up and run the suite.
create_test_globalrc '' '
[authentication]
    hashes = md5'
install_suite "${TEST_NAME_BASE}" basic
TEST_NAME="${TEST_NAME_BASE}-validate-md5"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
cylc run "${SUITE_NAME}"

# Scan to grab the suite's port.
sleep 5  # Wait for the suite to initialize.
TEST_NAME="${TEST_NAME_BASE}-new-scan-md5"
PORT=$(cylc scan -b -n $SUITE_NAME 'localhost' 2>'/dev/null' \
    | sed -e 's/.*@localhost://')

# Connect using SHA256 hash.
create_test_globalrc '' '
[authentication]
    hashes = sha256,md5'

# Connect using SHA256 hash.
TEST_NAME="${TEST_NAME_BASE}-new-scan-md5-sha256"
run_ok "${TEST_NAME}" cylc trigger "${SUITE_NAME}" bar 1
grep_ok "INFO - \[client-command\] trigger_task" "$(cylc cat-log -l $SUITE_NAME)"

# Shutdown using SHA256.
TEST_NAME="${TEST_NAME_BASE}-stop-md5-sha256"
run_ok "${TEST_NAME}" cylc stop --max-polls=10 --interval=1 "${SUITE_NAME}"

# Double check shutdown.
TEST_NAME="${TEST_NAME_BASE}-stop-md5"
sleep 2
run_fail "${TEST_NAME}" cylc stop --max-polls=10 --interval=1 "${SUITE_NAME}"

# Purge.
purge_suite "${SUITE_NAME}"
exit
