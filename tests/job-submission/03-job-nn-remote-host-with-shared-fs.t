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
#-------------------------------------------------------------------------------
# Test remote host (with shared fs) job log NN link correctness.
CYLC_TEST_IS_GENERIC=false
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
export CYLC_TEST_HOST=$( \
    cylc get-global-config -i '[test battery]remote host with shared fs' \
    2>'/dev/null')
if [[ -z "$CYLC_TEST_HOST" ]]; then
    skip_all '"[test battery]remote host with shared fs": not defined'
fi
set_test_number 2
#-------------------------------------------------------------------------------
install_suite "$TEST_NAME_BASE" "$TEST_NAME_BASE"
#-------------------------------------------------------------------------------
TEST_NAME="$TEST_NAME_BASE-validate"
run_ok "$TEST_NAME" cylc validate "$SUITE_NAME"
#-------------------------------------------------------------------------------
TEST_NAME="$TEST_NAME_BASE-run"
suite_run_ok "$TEST_NAME" cylc run --reference-test --debug --no-detach "$SUITE_NAME"
#-------------------------------------------------------------------------------
if [[ "$CYLC_TEST_HOST" != 'localhost' ]]; then
    purge_suite_remote "${CYLC_TEST_HOST}" "${SUITE_NAME}"
fi
purge_suite "$SUITE_NAME"
exit
