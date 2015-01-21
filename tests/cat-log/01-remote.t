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
# Test cat-log, remote host
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
export CYLC_TEST_HOST=$(cylc get-global-config -i '[test battery]remote host')
if [[ -z $CYLC_TEST_HOST ]]; then
    skip_all '[test battery]remote host: not defined'
fi
N_TESTS=4
set_test_number $N_TESTS
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
set -eu
ssh -oBatchMode=yes -oConnectTimeout=5 $CYLC_TEST_HOST \
    "mkdir -p .cylc/$SUITE_NAME/ && cat >.cylc/$SUITE_NAME/passphrase" \
    <$TEST_DIR/$SUITE_NAME/passphrase
set +eu
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --reference-test --debug $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-2
cylc cat-log -o $SUITE_NAME echo_2.1 >$TEST_NAME.out
grep_ok '^echo_2.1$' $TEST_NAME.out
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-3
cylc cat-log -o $SUITE_NAME echo_3.1 >$TEST_NAME.out
grep_ok '^echo_3.1$' $TEST_NAME.out
#-------------------------------------------------------------------------------
ssh -oBatchMode=yes -oConnectTimeout=5 $CYLC_TEST_HOST \
    "rm -rf .cylc/$SUITE_NAME cylc-run/$SUITE_NAME"
purge_suite $SUITE_NAME
exit
