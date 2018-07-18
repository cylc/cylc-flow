#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
set_test_number 4
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --no-detach --debug --no-detach $SUITE_NAME
#-------------------------------------------------------------------------------
# Test logging of client commands invoked by task foo.
UUID=$(cylc cat-log $SUITE_NAME | grep '\[client-connect].*cylc-hold' | awk '{print $7}')
cylc cat-log $SUITE_NAME | grep "\[client-.* $UUID" | sed -e 's/^.* - //' > log1.txt
CONTACT=$(cylc cat-log -f job.contact -m p $SUITE_NAME foo.1)
eval $(grep CYLC_SUITE_OWNER $CONTACT)
eval $(grep CYLC_SUITE_HOST $CONTACT)
# (in case of suite self-identification by IP address rather than hostname)
USER_AT_HOST=${CYLC_SUITE_OWNER}@${CYLC_SUITE_HOST}
cmp_ok log1.txt << __END__
[client-connect] ${USER_AT_HOST}:cylc-hold privilege='full-control' $UUID
[client-command] hold_suite ${USER_AT_HOST}:cylc-hold $UUID
[client-connect] ${USER_AT_HOST}:cylc-show privilege='full-control' $UUID
[client-command] get_suite_info ${USER_AT_HOST}:cylc-show $UUID
[client-connect] ${USER_AT_HOST}:cylc-broadcast privilege='full-control' $UUID
[client-command] get_broadcast ${USER_AT_HOST}:cylc-broadcast $UUID
[client-connect] ${USER_AT_HOST}:cylc-release privilege='full-control' $UUID
[client-command] release_suite ${USER_AT_HOST}:cylc-release $UUID
__END__
#-------------------------------------------------------------------------------
# Test logging of task messaging connections.
cylc cat-log $SUITE_NAME | grep "\[client-.*cylc-message" | awk '{print $4,$5,$6}' > log2.txt
cmp_ok log2.txt << __END__
[client-connect] ${USER_AT_HOST}:cylc-message privilege='full-control'
[client-command] put_messages ${USER_AT_HOST}:cylc-message
[client-connect] ${USER_AT_HOST}:cylc-message privilege='full-control'
[client-command] put_messages ${USER_AT_HOST}:cylc-message
__END__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
