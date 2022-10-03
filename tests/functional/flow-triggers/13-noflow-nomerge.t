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

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
DB="${WORKFLOW_RUN_DIR}/log/db"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}"
poll_grep_workflow_log "Workflow stalled"

run_ok "${TEST_NAME_BASE}-trigger" cylc trigger --flow=none "${WORKFLOW_NAME}//1/a"
poll_grep_workflow_log -E "1/a running job:02 flows:none.*=> succeeded"

cylc stop --now --now --max-polls=5 --interval=2 "$WORKFLOW_NAME"

TEST_NAME="${TEST_NAME_BASE}-count"
QUERY="SELECT COUNT(*) FROM task_states WHERE name=='a'"
run_ok "${TEST_NAME}" sqlite3 "${DB}" "$QUERY"
cmp_ok "${TEST_NAME}.stdout" <<__END__
2
__END__

QUERY="SELECT COUNT(*) FROM task_states WHERE name=='b'"
run_ok "${TEST_NAME}" sqlite3 "${DB}" "$QUERY"
cmp_ok "${TEST_NAME}.stdout" <<__END__
1
__END__

purge
