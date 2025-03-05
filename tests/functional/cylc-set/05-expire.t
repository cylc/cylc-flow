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

# "cylc set" proposal examples: 6 - check that forced task expiry works
# https://cylc.github.io/cylc-admin/proposal-cylc-set.html#6-expire-a-task

. "$(dirname "$0")/test_header"
set_test_number 4

install_and_validate
reftest_run

sqlite3 ~/cylc-run/"${WORKFLOW_NAME}"/log/db \
   "SELECT status FROM task_states WHERE name is 'bar'" > db-bar.1

cmp_ok "db-bar.1" - << __OUT__
expired
__OUT__

sqlite3 ~/cylc-run/"${WORKFLOW_NAME}"/log/db \
   "SELECT outputs FROM task_outputs WHERE name is 'bar'" > db-bar.2

cmp_ok "db-bar.2" - << __OUT__
{"expired": "(manually completed)"}
__OUT__

purge
