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
# Test "cylc cat-log" with bad suite name.
. "$(dirname "$0")/test_header"
set_test_number 4

CYLC_RUN_DIR="$(cylc get-global-config --print-run-dir)"
BAD_NAME="$(basename "$(mktemp -u "${CYLC_RUN_DIR}/XXXXXXXX")")"

run_fail "${TEST_NAME_BASE}-suite" cylc cat-log -f l "${BAD_NAME}"
cmp_ok "${TEST_NAME_BASE}-suite.stderr" <<__ERR__
UserInputError: The '-f' option is for job logs only.
__ERR__

run_fail "${TEST_NAME_BASE}-suite" cylc cat-log -f j "${BAD_NAME}" "garbage.1"
cmp_ok "${TEST_NAME_BASE}-suite.stderr" <<__ERR__
file not found: ${CYLC_RUN_DIR}/${BAD_NAME}/log/job/1/garbage/NN/job
__ERR__

exit
