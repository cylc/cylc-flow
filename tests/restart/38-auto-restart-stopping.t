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
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
CYLC_TEST_HOST="$( \
    cylc get-global-config -i '[test battery]remote host with shared fs' \
    2>'/dev/null')"
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip_all '"[test battery]remote host with shared fs": not defined'
fi
export CYLC_TEST_HOST
set_test_number 2
if ${CYLC_TEST_DEBUG:-false}; then ERR=2; else ERR=1; fi
#-------------------------------------------------------------------------------
# ensure that suites don't get auto stop-restarted if they are already stopping
BASE_GLOBALRC="
[cylc]
    [[main loop]]
        plugins = health check, auto restart
        [[[auto restart]]]
            interval = PT1S
    [[events]]
        abort on inactivity = True
        abort on timeout = True
        inactivity = PT1M
        timeout = PT1M
[suite servers]
    run hosts = localhost, ${CYLC_TEST_HOST}"

TEST_NAME="${TEST_NAME_BASE}"

init_suite "${TEST_NAME}" - <<'__SUITERC__'
[scheduling]
    [[graph]]
        R1 = foo => bar
[runtime]
    [[foo]]
        script = cylc stop "${CYLC_SUITE_NAME}"; sleep 15
__SUITERC__

create_test_globalrc '' "
${BASE_GLOBALRC}
"

run_ok "${TEST_NAME}-suite-start" cylc run "${SUITE_NAME}" --host=localhost
cylc suite-state "${SUITE_NAME}" --task='foo' --status='running' --point=1 \
    --interval=1 --max-polls=20 >& $ERR

# condemn localhost
create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    condemned hosts = $(hostname)
"

# wait for suite to die of natural causes
poll_suite_stopped
grep_ok 'Suite shutting down - REQUEST(CLEAN)' \
    "$(cylc cat-log "${SUITE_NAME}" -m p)"

exit
