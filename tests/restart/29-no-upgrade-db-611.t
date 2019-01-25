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
#-------------------------------------------------------------------------------
# Test ignore 6.11.X database if a 7.X database exists
. "$(dirname "$0")/test_header"

which sqlite3 > /dev/null || skip_all "sqlite3 not installed?"
set_test_number 3

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

sqlite3 "${SUITE_RUN_DIR}/cylc-suite-private.db" <"cylc-suite-db.dump"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run --debug --no-detach --until=2011 "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-restart" \
    cylc restart --debug --no-detach --reference-test "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
