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

. "$(dirname "$0")/test_header"

set_test_number 8

install_workflow "${TEST_NAME_BASE}" backcompat

# create Cylc 7 DB
run_ok "create-db" sqlite3 "${WORKFLOW_RUN_DIR}/log/db" < schema-1.sql

TEST_NAME="${TEST_NAME_BASE}_compat_1"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}"

contains_ok "${TEST_NAME}.stdout" <<__END__
2051/foo:succeeded
2051/bar:succeeded
__END__

# recreate Cylc 7 DB with one NULL status
rm "${WORKFLOW_RUN_DIR}/log/db"
run_ok "create-db" sqlite3 "${WORKFLOW_RUN_DIR}/log/db" < schema-2.sql

TEST_NAME="${TEST_NAME_BASE}_compat_2"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 "${WORKFLOW_NAME}"

contains_ok "${TEST_NAME}.stdout" <<__END__
2051/foo:succeeded
__END__

# Cylc 7 DB only contains custom outputs
TEST_NAME="${TEST_NAME_BASE}_outputs"
run_ok "${TEST_NAME}" cylc workflow-state --max-polls=1 --messages "${WORKFLOW_NAME}"

contains_ok "${TEST_NAME}.stdout" <<__END__
2051/foo:{'x': 'the quick brown fox'}
__END__

purge
