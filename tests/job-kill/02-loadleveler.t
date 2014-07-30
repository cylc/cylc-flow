#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test killing of jobs submitted to loadleveler.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
export CYLC_TEST_HOST=$( \
    cylc get-global-config -i '[test battery][directives]loadleveler host')
if [[ -z $CYLC_TEST_HOST ]]; then
    skip_all '[test battery][directives]loadleveler host: not defined'
fi
N_TESTS=2
set_test_number $N_TESTS
export CYLC_TEST_DIRECTIVES=$( \
    cylc get-global-config \
    -i '[test battery][directives][loadleveler directives]')
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
set -eu
if [[ $CYLC_TEST_HOST != 'localhost' ]]; then
    SSH='ssh -oBatchMode=yes -oConnectTimeout=5'
    $SSH $CYLC_TEST_HOST \
        "mkdir -p .cylc/$SUITE_NAME/ && cat >.cylc/$SUITE_NAME/passphrase" \
        <$TEST_DIR/$SUITE_NAME/passphrase
fi
set +eu
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --reference-test --debug $SUITE_NAME
#-------------------------------------------------------------------------------
if [[ $CYLC_TEST_HOST != 'localhost' ]]; then
    $SSH $CYLC_TEST_HOST \
        "rm -rf .cylc/$SUITE_NAME cylc-run/$SUITE_NAME"
fi
purge_suite $SUITE_NAME
exit
