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
# Test logging of user@host in response to suite connections.
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
cylc cat-log $SUITE_NAME | grep "Client" | awk '{print $5,$6,$7}' > log.txt
USER_AT_HOST=${USER}@$(hostname -f)
cmp_ok log.txt << __END__
hold_suite (cylc-hold ${USER_AT_HOST}
get_suite_info (cylc-show ${USER_AT_HOST}
get (cylc-broadcast ${USER_AT_HOST}
__END__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
