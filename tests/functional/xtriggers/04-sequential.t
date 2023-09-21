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

# Test xtrigger sequential spawning -
#   

. "$(dirname "$0")/test_header"

set_test_number 7

# Test workflow uses built-in 'echo' xtrigger.
init_workflow "${TEST_NAME_BASE}" << '__FLOW_CONFIG__'
[scheduler]
    cycle point format = %Y
    allow implicit tasks = True
[scheduling]
    initial cycle point = 3000
    runahead limit = P5
    sequential xtriggers default = True
    [[xtriggers]]
        clock_1 = wall_clock(offset=P2Y, sequential=False)
        clock_2 = wall_clock()
        up_1 = workflow_state(\
            workflow=%(workflow)s, \
            task=b, \
            point=%(point)s, \
            offset=-P1Y, \
            sequential=False \
        ):PT1S
    [[graph]]
        R1 = """
@clock_1 => a
b
"""
        +P1Y/P1Y = """
@clock_2 => a
@clock_2 => b
@up_1 => c
"""
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-val" cylc validate "${WORKFLOW_NAME}"

# Run workflow; it will stall waiting on the never-satisfied xtriggers.
cylc play "${WORKFLOW_NAME}"

poll_grep_workflow_log -E '3001/c/.* => succeeded'

cylc stop --max-polls=10 --interval=2 "${WORKFLOW_NAME}"

cylc play "${WORKFLOW_NAME}"

cylc show "${WORKFLOW_NAME}//3001/a" | grep -E 'state: ' > 3001.a.log
cylc show "${WORKFLOW_NAME}//3002/a" 2>&1 >/dev/null \
    | grep -E 'No matching' > 3002.a.log

# 3001/a should be spawned at both 3000/3001.
cmp_ok 3001.a.log - <<__END__
state: waiting
__END__
# 3002/a should not exist.
cmp_ok 3002.a.log - <<__END__
No matching active tasks found: 3002/a
__END__

cylc reload "${WORKFLOW_NAME}"

cylc remove "${WORKFLOW_NAME}//3001/b"

cylc show "${WORKFLOW_NAME}//3002/b" | grep -E 'state: ' > 3002.b.log
cylc show "${WORKFLOW_NAME}//3003/b" 2>&1 >/dev/null \
    | grep -E 'No matching' > 3003.b.log

# 3002/b should be only at 3002.
cmp_ok 3002.b.log - <<__END__
state: waiting
__END__
cmp_ok 3003.b.log - <<__END__
No matching active tasks found: 3003/b
__END__

cylc show "${WORKFLOW_NAME}//3002/c" | grep -E 'state: ' > 3002.c.log
cylc show "${WORKFLOW_NAME}//3005/c" | grep -E 'state: ' > 3005.c.log

# c should be from 3002-3005.
cmp_ok 3002.c.log - <<__END__
state: waiting
__END__
cmp_ok 3005.c.log - <<__END__
state: waiting
__END__


cylc stop --now --max-polls=10 --interval=2 "${WORKFLOW_NAME}"
purge
exit
