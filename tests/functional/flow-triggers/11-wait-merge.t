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
set_test_number 4

install_and_validate "${TEST_NAME_BASE}" "${TEST_NAME_BASE}" true
DB="${WORKFLOW_RUN_DIR}/runN/log/db"

reftest_run

TEST_NAME="${TEST_NAME_BASE}-order-no-wait"
QUERY="SELECT cycle, name,flow_nums,outputs FROM task_outputs;"

run_ok "${TEST_NAME}" sqlite3 "${DB}" "$QUERY"

cmp_ok "${TEST_NAME}.stdout" <<\__END__
1|a|[1]|["submitted", "started", "succeeded"]
1|b|[1]|["submitted", "started", "succeeded"]
1|a|[2]|["submitted", "started", "succeeded"]
1|c|[2]|["submitted", "started", "x"]
1|c|[1, 2]|["submitted", "started", "succeeded", "x"]
1|x|[1, 2]|["submitted", "started", "succeeded"]
1|d|[1, 2]|["submitted", "started", "succeeded"]
1|b|[2]|["submitted", "started", "succeeded"]
__END__

purge
