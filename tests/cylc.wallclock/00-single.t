#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Unit test parts of lib/isodatetime/wallclock.py.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 7
export PYTHONPATH=$CYLC_DIR/lib:$PYTHONPATH

# Arguments: TEST_NAME TIME_STRING EXPECTED_UNIX_TIME CALENDAR_IS_360
function test_get_unix_time_from_time_string () {
    run_ok $1 python <<__PYTHON__
from cylc.flow.wallclock import get_unix_time_from_time_string

if $4:
    from isodatetime.data import CALENDAR
    CALENDAR.set_mode(CALENDAR.MODE_360)
assert(get_unix_time_from_time_string('$2') == $3)
__PYTHON__
}
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get_unix_time_from_time_string-greg-1
test_get_unix_time_from_time_string $TEST_NAME '2016-09-08T09:09:00+01' 1473322140 False
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get_unix_time_from_time_string-greg-2
test_get_unix_time_from_time_string $TEST_NAME '2016-09-08T08:09:00Z' 1473322140 False
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get_unix_time_from_time_string-greg-3
test_get_unix_time_from_time_string $TEST_NAME '2016-09-07T20:09:00-12' 1473322140 False
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get_unix_time_from_time_string-360-1
test_get_unix_time_from_time_string $TEST_NAME '2016-09-08T09:09:00+01' 1473322140 True
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get_unix_time_from_time_string-360-2
test_get_unix_time_from_time_string $TEST_NAME '2016-09-08T08:09:00Z' 1473322140 True
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get_unix_time_from_time_string-360-3
test_get_unix_time_from_time_string $TEST_NAME '2016-09-07T20:09:00-12' 1473322140 True
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get_unix_time_from_time_string-360-31-1
test_get_unix_time_from_time_string $TEST_NAME '2016-08-31T18:09:00+01' 1472663340 True
exit
