#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
#-------------------------------------------------------------------------------
# Test validation for a bad recurrences
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 10

TEST_NAME="${TEST_NAME_BASE}-interval"
cat >'suite.rc' <<'__SUITE__'
[cylc]
    cycle point time zone = +01
[scheduling]
    initial cycle point = 20140101T00
    final cycle point = 20140201T00
    [[graph]]
        # PT5D is invalid - should be P5D
        R/T00/PT5D = "foo"
[runtime]
    [[foo]]
        script = true
__SUITE__
run_fail "${TEST_NAME}" cylc validate 'suite.rc'
cmp_ok "${TEST_NAME}.stderr" <<'__ERR__'
SuiteConfigError: Cannot process recurrence R/T00/PT5D (initial cycle point=20140101T0000+01) (final cycle point=20140201T0000+01)
__ERR__

TEST_NAME="${TEST_NAME_BASE}-old-icp"
cat >'suite.rc' <<'__SUITE__'
[cylc]
    UTC mode = True
[scheduling]
    initial cycle point = 20140101
    [[graph]]
        R1/P0D = "foo => final_foo"
[runtime]
    [[root]]
        script = true
__SUITE__
run_fail "${TEST_NAME}" cylc validate 'suite.rc'
cmp_ok "${TEST_NAME}.stderr" <<'__ERR__'
SuiteConfigError: Cannot process recurrence R1/P0D (initial cycle point=20140101T0000Z) (final cycle point=None) This suite requires a final cycle point.
__ERR__

TEST_NAME="${TEST_NAME_BASE}-2-digit-century"
cat >'suite.rc' <<'__SUITE__'
[cylc]
    cycle point time zone = +01
[scheduling]
    initial cycle point = 20140101T00
    final cycle point = 20140201T00
    [[graph]]
        # Users may easily write 00 where they mean T00 or '0' in old syntax.
        # Technically 00 means the year 0000, but we won't allow it in Cylc.
        R/00/P5D = "foo"
[runtime]
    [[foo]]
        script = true
__SUITE__
run_fail "${TEST_NAME}" cylc validate 'suite.rc'
cmp_ok "${TEST_NAME}.stderr" <<'__ERR__'
SuiteConfigError: Cannot process recurrence R/00/P5D (initial cycle point=20140101T0000+01) (final cycle point=20140201T0000+01) '00': 2 digit centuries not allowed. Did you mean T-digit-digit e.g. 'T00'?
__ERR__

TEST_NAME="${TEST_NAME_BASE}-old-recurrences"
cat >'suite.rc' <<'__SUITE__'
[cylc]
    cycle point time zone = +01
[scheduling]
    initial cycle point = 20100101T00
    [[graph]]
        0,6,12 = "foo"
__SUITE__
run_fail "${TEST_NAME}" cylc validate 'suite.rc'
cmp_ok "${TEST_NAME}.stderr" <<'__ERR__'
SuiteConfigError: Cannot process recurrence 0 (initial cycle point=20100101T0000+01) (final cycle point=None) '0': not a valid cylc-shorthand or full ISO 8601 date representation
__ERR__

TEST_NAME="${TEST_NAME_BASE}-old-cycle-point-format"
cat >'suite.rc' <<'__SUITE__'
[cylc]
    cycle point format = %Y%m%d%H
[scheduling]
    initial cycle point = 2010010101
    [[graph]]
        R1 = foo
__SUITE__
run_fail "${TEST_NAME}" cylc validate 'suite.rc'
cmp_ok "${TEST_NAME}.stderr" <<'__ERR__'
SuiteConfigError: Cannot process recurrence R1 (initial cycle point=2010010101) (final cycle point=None) '2010010101': not a valid cylc-shorthand or full ISO 8601 date representation
__ERR__

exit
