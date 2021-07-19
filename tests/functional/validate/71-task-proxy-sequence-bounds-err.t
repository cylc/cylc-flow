#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

# Test for handling task proxy sequence bounds error. #2735

. "$(dirname "$0")/test_header"
set_test_number 4

cat > flow.cylc <<__END__
[scheduler]
    UTC mode = True
[scheduling]
    initial cycle point = 2000
    [[graph]]
        R1//1999 = t1
[runtime]
    [[t1]]
        script = true
__END__

TEST_NAME="${TEST_NAME_BASE}-single"
run_ok "$TEST_NAME" cylc validate 'flow.cylc'
cmp_ok "${TEST_NAME}.stderr" <<'__ERR__'
WARNING - R1/P0Y/19990101T0000Z: sequence out of bounds for initial cycle point 20000101T0000Z
__ERR__

cat > flow.cylc <<__END__
[scheduler]
    UTC mode = True
[scheduling]
    initial cycle point = 2000
    [[graph]]
        R1//1996, R1//1997, R1//1998, R1//1999 = t1
[runtime]
    [[t1]]
        script = true
__END__

TEST_NAME="${TEST_NAME_BASE}-multiple"
run_ok "$TEST_NAME" cylc validate 'flow.cylc'
contains_ok "${TEST_NAME}.stderr" <<'__ERR__'
WARNING - multiple sequences out of bounds for initial cycle point 20000101T0000Z:
	R1/P0Y/19960101T0000Z, R1/P0Y/19970101T0000Z, R1/P0Y/19980101T0000Z,
	R1/P0Y/19990101T0000Z
__ERR__

exit
