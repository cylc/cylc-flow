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
# Test set stop point then reload. Reload should not reset stop point.
# https://github.com/cylc/cylc-flow/issues/2964
export REQUIRE_PLATFORM='runner:at'
. "$(dirname "$0")/test_header"
set_test_number 3

create_test_global_config "
[platforms]
    [[$CYLC_TEST_PLATFORM]]
        job runner command template = sleep 5
        submission retry delays = 3*PT5S
"

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach --reference-test "${SUITE_NAME}"
sqlite3 "${SUITE_RUN_DIR}/.service/db" \
    'SELECT cycle,name,run_status FROM task_jobs' | sort >'db.out'
cmp_ok 'db.out' <<'__OUT__'
1|reload|0
1|set-stop-point|0
1|t1|0
2|t1|0
3|t1|0
__OUT__

purge
exit
