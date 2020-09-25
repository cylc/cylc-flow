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
# Test warm start persists across restarts
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 6
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" warm-start
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-run-hold
suite_run_ok "${TEST_NAME}" cylc run --warm "${SUITE_NAME}" 20130101T12 --hold
#-------------------------------------------------------------------------------
cylc stop --max-polls=10 --interval=2 "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-run-hold-restart
suite_run_ok "${TEST_NAME}" cylc restart "${SUITE_NAME}"
# Ensure suite has started
poll_suite_running
#-------------------------------------------------------------------------------
# Check pre-reqs
TEST_NAME=${TEST_NAME_BASE}-check-prereq
run_ok "${TEST_NAME}" cylc show "${SUITE_NAME}" foo.20130101T1200Z --list-prereqs
cmp_ok "${TEST_NAME}.stdout" <<'__OUT__'
__OUT__
#-------------------------------------------------------------------------------
# Stop suite
cylc stop --max-polls=10 --interval=2 "${SUITE_NAME}"
#-------------------------------------------------------------------------------
DB_FILE="${RUN_DIR}/${SUITE_NAME}/log/db"
NAME='database-entry'
sqlite3 "${DB_FILE}" \
    'SELECT value FROM suite_params WHERE key=="startcp"' >"${NAME}"
cmp_ok "${NAME}" <<<'20130101T12'
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
