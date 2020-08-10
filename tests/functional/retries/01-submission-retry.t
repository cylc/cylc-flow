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
# Test execution retries are working
. "$(dirname "$0")/test_header"
set_test_number 3
install_suite "${TEST_NAME_BASE}" 'submission'
create_test_globalrc "" "
[platforms]
[[nonsense-platform]]
hosts = notahost
"

#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
if ! command -v 'sqlite3' >'/dev/null'; then
    sqlite3 \
        "$RUN_DIR/${SUITE_NAME}/log/db" \
        'SELECT try_num, submit_num FROM task_jobs' >'select.out'
    cmp_ok 'select.out' <<'__OUT__'
1|1
1|2
1|3
1|4
__OUT__
else
    skip 1 'sqlite3 not installed?'
fi
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
