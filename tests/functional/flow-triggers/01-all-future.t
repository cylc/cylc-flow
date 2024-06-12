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
#-------------------------------------------------------------------------------

. "$(dirname "$0")/test_header"
set_test_number 7

install_and_validate "${TEST_NAME_BASE}" "${TEST_NAME_BASE}" true
DB="${WORKFLOW_RUN_DIR}/runN/log/db"

reftest_run

TEST_NAME="${TEST_NAME_BASE}-order-no-wait"
QUERY="SELECT name,flow_nums,flow_wait FROM task_states\
 WHERE name IN ('a','d','c','e') ORDER BY time_created;"
run_ok "${TEST_NAME}" sqlite3 "${DB}" "$QUERY"
# If not waiting, e should come before c.
cmp_ok "${TEST_NAME}.stdout" <<\__END__
a|[1]|0
d|[1]|0
e|[1]|0
c|[1]|0
__END__

export REFTEST_OPTS=--set="WAIT=1"
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}" true
reftest_run

TEST_NAME="${TEST_NAME_BASE}-order-wait"
# Note flow_wait is updated to False once used.
QUERY="SELECT name,flow_nums,flow_wait FROM task_states ORDER BY time_created"
run_ok "${TEST_NAME}" sqlite3 "${DB}" "$QUERY"
cmp_ok "${TEST_NAME}.stdout" <<\__END__
a|[1]|0
d|[1]|0
b|[1]|0
c|[1]|0
e|[1]|0
f|[1]|0
__END__

purge
