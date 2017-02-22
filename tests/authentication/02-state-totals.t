#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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

# Test authentication - privilege 'state-totals'.

. $(dirname $0)/test_header
set_test_number 7

install_suite "${TEST_NAME_BASE}" basic

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

# Run the suite.
create_test_globalrc '' '
[authentication]
    public = state-totals'
cylc run "${SUITE_NAME}"
unset CYLC_CONF_PATH

# Wait for first task 'foo' to fail.
cylc suite-state "${SUITE_NAME}" --task=foo --status=failed --point=1 \
    --interval=1 --max-polls=10 || exit 1

# Disable the suite passphrase (to leave us with public access privilege).
SRV_D="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/.service"
mv "${SRV_D}/passphrase" "${SRV_D}/passphrase.DIS"

# Check scan output.
PORT=$(cylc ping -v "${SUITE_NAME}" | cut -d':' -f 2)
cylc scan --comms-timeout=5 -fb -n "${SUITE_NAME}" 'localhost' \
    >'scan.out'
cmp_ok scan.out << __END__
${SUITE_NAME} ${USER}@localhost:${PORT}
   Title:
      "Authentication test suite."
   Description:
      "Stalls when the first task fails."
   Task state totals:
      failed:1 waiting:1
      1 failed:1 waiting:1
__END__

# "cylc show" (suite info) OK.
TEST_NAME="${TEST_NAME_BASE}-show1"
run_ok "${TEST_NAME}" cylc show "${SUITE_NAME}"

# "cylc show" (task info) should be denied.
TEST_NAME="${TEST_NAME_BASE}-show2"
run_fail "${TEST_NAME}" cylc show "${SUITE_NAME}" foo.1
cylc log "${SUITE_NAME}" > suite.log1
grep_ok "\[client-connect] DENIED (privilege 'state-totals' < 'full-read') ${USER}@.*:cylc-show" suite.log1

# Commands should be denied.
TEST_NAME="${TEST_NAME_BASE}-stop"
run_fail "${TEST_NAME}" cylc stop "${SUITE_NAME}"
cylc log "${SUITE_NAME}" > suite.log2
grep_ok "\[client-connect] DENIED (privilege 'state-totals' < 'shutdown') ${USER}@.*:cylc-stop" suite.log2

# Restore the passphrase.
mv "${SRV_D}/passphrase.DIS" "${SRV_D}/passphrase"

# Stop and purge the suite.
cylc stop --max-polls=20 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
