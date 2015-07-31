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

# Test authentication - privilege 'full-control' (with passphrase).

. $(dirname $0)/test_header
set_test_number 9

install_suite "${TEST_NAME_BASE}" basic

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

# Run the suite.
# Set public auth low to test that passphrase gives full control
cat > global.rc << __END__
[authentication]
    public = identity
__END__
CYLC_CONF_PATH="${PWD}" cylc run "${SUITE_NAME}"

# Wait for first task 'foo' to fail.
cylc suite-state "${SUITE_NAME}" --task=foo --status=failed --cycle=1 \
    --interval=1 --max-polls=10 || exit 1

# Check scan output.
PORT=$(cylc ping -v "${SUITE_NAME}" | awk '{print $4}')
cylc scan -fb -n "${SUITE_NAME}" localhost > scan.out
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
cylc log "${SUITE_NAME}" > suite.log1
grep_ok "\[client-command] get_suite_info ${USER}@.*:cylc-show" suite.log1

# "cylc show" (task info) OK.
TEST_NAME="${TEST_NAME_BASE}-show2"
run_ok "${TEST_NAME}" cylc show "${SUITE_NAME}" foo.1
cylc log "${SUITE_NAME}" > suite.log2
grep_ok "\[client-command] get_task_info ${USER}@.*:cylc-show" suite.log2

# Commands OK.
# (Reset to same state).
TEST_NAME="${TEST_NAME_BASE}-trigger"
run_ok "${TEST_NAME}" cylc reset "${SUITE_NAME}" -s failed foo 1
cylc log "${SUITE_NAME}" > suite.log3
grep_ok "\[client-command] reset_task_state ${USER}@.*:cylc-reset" suite.log3

# Shutdown and purge.
TEST_NAME="${TEST_NAME_BASE}-stop"
run_ok "${TEST_NAME}" cylc stop --max-polls=10 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
