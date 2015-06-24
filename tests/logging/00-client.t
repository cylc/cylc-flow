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
# Test logging of client connections and commands.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 3
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --no-detach --debug $SUITE_NAME
#-------------------------------------------------------------------------------
cylc cat-log $SUITE_NAME | grep "client" | awk '{print $5,$6,$7}' > log.txt
USER_AT_HOST=${USER}@$(hostname -f)
cmp_ok log.txt << __END__
connect ${USER_AT_HOST}:cylc-message privilege='full-control'
command task_message ${USER_AT_HOST}:cylc-message
connect ${USER_AT_HOST}:cylc-hold privilege='full-control'
command hold_suite ${USER_AT_HOST}:cylc-hold
connect ${USER_AT_HOST}:cylc-show privilege='full-control'
command get_suite_info ${USER_AT_HOST}:cylc-show
connect ${USER_AT_HOST}:cylc-broadcast privilege='full-control'
command broadcast_get ${USER_AT_HOST}:cylc-broadcast
connect ${USER_AT_HOST}:cylc-release privilege='full-control'
command release_suite ${USER_AT_HOST}:cylc-release
connect ${USER_AT_HOST}:cylc-message privilege='full-control'
command task_message ${USER_AT_HOST}:cylc-message
__END__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
