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

# Test xtrigger cycle-point specificity -
#   https://github.com/cylc/cylc-flow/issues/3283

. "$(dirname "$0")/test_header"

set_test_number 3

# Test workflow uses built-in 'echo' xtrigger.
init_workflow "${TEST_NAME_BASE}" << '__FLOW_CONFIG__'
[scheduler]
   cycle point format = %Y
[scheduling]
   initial cycle point = 2025
   final cycle point = +P1Y
   [[xtriggers]]
       e1 = echo(name='bob')
       e2 = echo(name='alice')
   [[dependencies]]
      [[[R1]]]
          graph = "start"
      [[[R/^/P2Y]]]
          graph = "@e1 => foo"
      [[[R/^+P1Y/P2Y]]]
          graph = "@e2 => foo"
[runtime]
   [[start]]
   [[foo]]
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-val" cylc validate 'flow.cylc'

# Run workflow; it will stall waiting on the never-satisfied xtriggers.
cylc play "${WORKFLOW_NAME}"

poll_grep_workflow_log 'start.2025.*succeeded'

cylc show "${WORKFLOW_NAME}" foo.2025 | grep -E '^  - xtrigger' > foo.2025.log
cylc show "${WORKFLOW_NAME}" foo.2026 | grep -E '^  - xtrigger' > foo.2026.log

# foo.2025 should get only xtrigger e1.
cmp_ok foo.2025.log - <<__END__
  - xtrigger "e1 = echo(name=bob)"
__END__

# foo.2026 should get only xtrigger e2.
cmp_ok foo.2026.log - <<__END__
  - xtrigger "e2 = echo(name=alice)"
__END__

cylc stop --now --max-polls=10 --interval=2 "${WORKFLOW_NAME}"
purge
exit
