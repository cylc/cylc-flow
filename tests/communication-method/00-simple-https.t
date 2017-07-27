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
# Test cylc scan is picking up running suite
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
create_test_globalrc '
[communication]
    method=https'
#-------------------------------------------------------------------------------
install_suite ${TEST_NAME_BASE} simple
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-validate
run_ok ${TEST_NAME} cylc validate ${SUITE_NAME}
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-check-suite-contact-https
cylc run ${SUITE_NAME} --hold
cylc get-suite-contact ${SUITE_NAME} | grep "CYLC_COMMS_PROTOCOL=https" > log1.txt 
cylc release ${SUITE_NAME}
cmp_ok log1.txt << __END__
CYLC_COMMS_PROTOCOL=https
__END__
#-------------------------------------------------------------------------------
purge_suite ${SUITE_NAME}
exit

