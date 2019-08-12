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

# Test xtrigger cycle-point specificity -
#   https://github.com/cylc/cylc-flow/issues/3283

. "$(dirname "$0")/test_header"

set_test_number 3

# Test suite uses built-in 'echo' xtrigger.
init_suite "${TEST_NAME_BASE}" << '__SUITE_RC__'
[cylc]
   cycle point format = %Y
[scheduling]
   initial cycle point = 2025
   final cycle point = +P1Y
   spawn to max active cycle points = True
   [[xtriggers]]
       e1 = echo(name='bob')
       e2 = echo(name='alice')
   [[dependencies]]
      [[[R/^/P2Y]]]
          graph = "@e1 => foo"
      [[[R/^+P1Y/P2Y]]]
          graph = "@e2 => foo"
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-val" cylc validate 'suite.rc'

# Run suite; it will stall waiting on the never-satisfied xtriggers.
cylc run "${SUITE_NAME}"

sleep 5

cylc show "${SUITE_NAME}" foo.2025 | egrep '^  o' > foo.2025.log
cylc show "${SUITE_NAME}" foo.2026 | egrep '^  o' > foo.2026.log

# foo.2025 should get only xtrigger e1.
cmp_ok foo.2025.log - <<__END__
  o  xtrigger "e1" ... NOT satisfied
__END__

# foo.2026 should get only xtrigger e2.
cmp_ok foo.2026.log - <<__END__
  o  xtrigger "e2" ... NOT satisfied
__END__

cylc stop --now "${SUITE_NAME}"
