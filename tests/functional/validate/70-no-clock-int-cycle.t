#!/bin/bash
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

# Test that clock xtriggers are not allowed with integer cycling.
. "$(dirname "$0")/test_header"

set_test_number 2

cat >'suite.rc' <<'__SUITE_RC__'
[scheduling]
   cycling mode = integer
   initial cycle point = 1
   final cycle point = 2
   [[xtriggers]]
       c1 = wall_clock(offset=P0Y)
   [[graph]]
      R/^/P1 = "@c1 & foo[-P1] => foo"
__SUITE_RC__

run_fail "${TEST_NAME_BASE}-val" cylc validate 'suite.rc'

contains_ok "${TEST_NAME_BASE}-val.stderr" <<'__END__'
SuiteConfigError: clock xtriggers need date-time cycling: c1 = wall_clock(offset=P0Y)
__END__
