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
# Test "cylc cat-log --tail" with a custom local tail command.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 4
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
# Run detached so we get suite out and err logs.
suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"
#-------------------------------------------------------------------------------
mkdir 'conf'
export CYLC_CONF_PATH="${PWD}/conf"
cat > "$PWD/conf/global.rc" <<__GLOBAL_RC__
[hosts]
   [[localhost]]
        local tail command template = $PWD/bin/my-tailer.sh %(filename)s
__GLOBAL_RC__
#-------------------------------------------------------------------------------
sleep 10
TEST_NAME=$TEST_NAME_BASE-cat-log
cylc cat-log $SUITE_NAME -o --tail foo.1 > ${TEST_NAME}.out
grep_ok "HELLO from foo 1" ${TEST_NAME}.out
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-stop
run_ok $TEST_NAME cylc stop --kill --max-polls=10 --interval=1 $SUITE_NAME
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
