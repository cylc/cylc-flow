#!/bin/bash
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
# Test task submit failed + reload
# https://github.com/cylc/cylc-flow/issues/2964
. "$(dirname "$0")/test_header"

skip_all "TODO fix after sorting remote-init"

skip_darwin 'atrun hard to configure on Mac OS'

set_test_number 4

create_test_globalrc '
[job platforms]
    [[platypus]]
        batch system = at
        batch submit command template = sleep 5
        submission retry delays = 3*PT5S
'

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    "${TEST_DIR}/${SUITE_NAME}/bin/mycylcrun" \
    --debug --no-detach --reference-test "${SUITE_NAME}"
sqlite3 "${SUITE_RUN_DIR}/.service/db" \
    'SELECT name,status FROM task_states WHERE name=="t1"' >'db.out'
cmp_ok 'db.out' <<'__OUT__'
t1|submit-failed
__OUT__
sqlite3 "${SUITE_RUN_DIR}/.service/db" \
    'SELECT cycle,name,submit_num,run_status FROM task_jobs' | sort >'db.out'
cmp_ok 'db.out' <<'__OUT__'
1|reloader|1|0
1|stopper|1|0
1|t1|1|
1|t1|2|
1|t1|3|
1|t1|4|
__OUT__

purge_suite "${SUITE_NAME}"
exit
