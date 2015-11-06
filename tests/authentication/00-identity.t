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

# Test authentication - privilege 'identity'.

. $(dirname $0)/test_header
set_test_number 6

install_suite "${TEST_NAME_BASE}" basic

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

# Run the suite.
cat > global.rc << __END__
[authentication]
    public = identity
__END__
CYLC_CONF_PATH="${PWD}" cylc run "${SUITE_NAME}"

# Wait for first task 'foo' to fail.
cylc suite-state "${SUITE_NAME}" --task=foo --status=failed --cycle=1 \
    --interval=1 --max-polls=10 || exit 1

# Disable the suite passphrase (to leave us with public access privilege).
mv "${TEST_DIR}/${SUITE_NAME}/passphrase" \
    "${TEST_DIR}/${SUITE_NAME}/passphrase.DIS"

# Check scan output.
PORT=$(cylc ping -v "${SUITE_NAME}" | awk '{print $4}')
cylc scan -fb -n "${SUITE_NAME}" 'localhost' >'scan.out' 2>'/dev/null'
cmp_ok scan.out << __END__
${SUITE_NAME} ${USER}@localhost:${PORT}
   (description and state totals withheld)
__END__

# "cylc show" should be denied.
TEST_NAME="${TEST_NAME_BASE}-show"
run_fail "${TEST_NAME}" cylc show "${SUITE_NAME}"
cylc log "${SUITE_NAME}" > suite.log1
grep_ok "\[client-connect] DENIED (privilege 'identity' < 'description') ${USER}@.*:cylc-show" suite.log1

# Commands should be denied.
TEST_NAME="${TEST_NAME_BASE}-stop"
run_fail "${TEST_NAME}" cylc stop "${SUITE_NAME}"
cylc log "${SUITE_NAME}" > suite.log2
grep_ok "\[client-connect] DENIED (privilege 'identity' < 'shutdown') ${USER}@.*:cylc-stop" suite.log2

# Restore the passphrase.
mv "${TEST_DIR}/${SUITE_NAME}/passphrase.DIS" \
    "${TEST_DIR}/${SUITE_NAME}/passphrase"

# Stop and purge the suite.
cylc stop --max-polls=10 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
